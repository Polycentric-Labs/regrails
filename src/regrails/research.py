"""Perplexity Sonar research client (via OpenRouter).

POSTs to ``https://openrouter.ai/api/v1/chat/completions``. The API key is read
from ``OPENROUTER_API_KEY`` in the environment OR from an env-file at the path
``OPENROUTER_ENV_FILE`` (defaults to ``~/.secrets/openrouter.env``) — never as
a tool argument, never reflected back to stdout, per the project's
secret-handling protocol.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, cast

import httpx

from .audit import EventAction, emit_event
from .models import ResearchSnapshot

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT_SECONDS = 120.0  # Sonar deep-research can take >60s


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter returns a non-200 response or empty body."""


# ---------------------------------------------------------------------------
# Secret loading
# ---------------------------------------------------------------------------


_ENV_LINE_RE = re.compile(r"^\s*(?P<key>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<val>.*?)\s*$")


def _default_env_file() -> Path:
    return Path.home() / ".secrets" / "openrouter.env"


def load_api_key(*, env_file: Path | None = None) -> str:
    """Return the OpenRouter API key.

    Resolution order:
        1. ``OPENROUTER_API_KEY`` already set in the process environment
        2. The first matching ``OPENROUTER_API_KEY=...`` line in the env file
           (path from ``OPENROUTER_ENV_FILE`` env-var, or argument, or default)

    Raises:
        FileNotFoundError: if no env var AND no env file.
        OpenRouterError:   if the env file exists but contains no key.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key

    path = env_file or Path(os.environ.get("OPENROUTER_ENV_FILE", _default_env_file()))
    if not path.exists():
        raise FileNotFoundError(
            f"OPENROUTER_API_KEY not set and env file not found at {path}"
        )

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _ENV_LINE_RE.match(line)
        if match and match.group("key") == "OPENROUTER_API_KEY":
            val = match.group("val")
            # Strip surrounding quotes if present
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            if val:
                return val
    raise OpenRouterError(f"OPENROUTER_API_KEY line not found in {path}")


# ---------------------------------------------------------------------------
# HTTP call
# ---------------------------------------------------------------------------


def chat_completion(
    *,
    model: str,
    messages: list[dict[str, str]],
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    extra_body: dict[str, Any] | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Call OpenRouter chat-completions and return the parsed JSON body.

    Caller provides ``api_key`` or RegRails resolves it via ``load_api_key()``.
    """
    if api_key is None:
        api_key = load_api_key()

    body: dict[str, Any] = {"model": model, "messages": messages}
    if extra_body:
        body.update(extra_body)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Polycentric-Labs/regrails",
        "X-Title": "RegRails",
    }

    client = http_client or httpx.Client(timeout=timeout)
    own_client = http_client is None
    try:
        resp = client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            json=body,
            headers=headers,
        )
        if resp.status_code != 200:
            raise OpenRouterError(
                f"OpenRouter returned {resp.status_code}: {resp.text[:300]}"
            )
        parsed = resp.json()
        if not isinstance(parsed, dict) or "choices" not in parsed:
            raise OpenRouterError(f"Malformed OpenRouter response: {resp.text[:300]}")
        return cast(dict[str, Any], parsed)
    finally:
        if own_client:
            client.close()


# ---------------------------------------------------------------------------
# Stream runner — wraps chat_completion + builds a ResearchSnapshot
# ---------------------------------------------------------------------------


def run_research_stream(
    *,
    stream_name: str,
    query: str,
    model: str,
    api_key: str | None = None,
    audit_sink: Path | None = None,
    http_client: httpx.Client | None = None,
) -> ResearchSnapshot:
    """Run one Perplexity Sonar query, return a populated ResearchSnapshot.

    ``stream_name`` is the slug under which the snapshot will eventually be
    persisted (e.g. ``"ferpa-ai-ambiguities"``). The snapshot's ``id`` is
    ``f"{stream_name}-{uuid4}"``.
    """
    snap_id = f"{stream_name}-{uuid.uuid4().hex[:8]}"
    started_at = time.monotonic()
    try:
        response = chat_completion(
            model=model,
            messages=[{"role": "user", "content": query}],
            api_key=api_key,
            http_client=http_client,
        )
    except Exception as exc:
        if audit_sink is not None:
            emit_event(
                EventAction.RESEARCH_STREAM_FAILED,
                payload={
                    "stream_name": stream_name,
                    "model": model,
                    "error": str(exc)[:300],
                },
                sink=audit_sink,
            )
        raise

    elapsed_ms = int((time.monotonic() - started_at) * 1000)

    choices = response.get("choices") or []
    content = ""
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content") or ""

    raw_citations = response.get("citations") or []
    citations: list[dict[str, str | int | float | None]] = []
    for c in raw_citations:
        if isinstance(c, str):
            citations.append({"url": c})
        elif isinstance(c, dict):
            citations.append(
                {k: v for k, v in c.items() if isinstance(v, (str, int, float)) or v is None}
            )

    usage = response.get("usage") or {}
    cost_usd: float | None = None
    if isinstance(usage, dict):
        cost = usage.get("cost") or usage.get("total_cost_usd")
        if isinstance(cost, (int, float)):
            cost_usd = float(cost)

    snapshot = ResearchSnapshot(
        id=snap_id,
        stream_name=stream_name,
        query=query,
        model=model,
        response_text=content,
        citations=citations,
        cost_usd=cost_usd,
    )

    if audit_sink is not None:
        emit_event(
            EventAction.RESEARCH_STREAM_FETCHED,
            payload={
                "stream_name": stream_name,
                "model": model,
                "snapshot_id": snap_id,
                "elapsed_ms": elapsed_ms,
                "response_chars": len(content),
                "citations_count": len(citations),
                "cost_usd": cost_usd,
            },
            sink=audit_sink,
        )

    return snapshot
