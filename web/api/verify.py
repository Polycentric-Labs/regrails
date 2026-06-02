"""Vercel Python serverless function: verify a hash-chained decision log.

POST the raw chain text (a JSONL hash chain, as written by ``regrails audit``) — or a
JSON body ``{"log": "<chain text>"}`` — and get back ``{"ok": bool, "problems": [...]}``.

Engine-only — no LLM, no API key, no secrets. This REUSES the published package's
``regrails.audit.verify_chain`` so the web verdict is identical to the CLI
``regrails audit verify`` verdict (single source of truth; guaranteed parity).
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def verify_payload(text: str) -> tuple[bool, list[str]]:
    """Verify the chain text ``text`` by delegating to ``regrails.audit.verify_chain``.

    Writes ``text`` to a temporary file, verifies it, then deletes the file. Returns
    ``verify_chain``'s own ``(ok, problems)`` so the result matches the CLI exactly.
    Empty or malformed input yields ``(False, [...])`` from ``verify_chain`` rather
    than raising.
    """
    from regrails.audit import verify_chain

    # mkstemp (not a `with NamedTemporaryFile`) so the file is fully closed before
    # verify_chain reopens it — on Windows an open temp file cannot be reopened. We
    # write, close, verify, then unlink in finally.
    fd, tmp_name = tempfile.mkstemp(suffix=".jsonl")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(text or "")
        result: tuple[bool, list[str]] = verify_chain(Path(tmp_name))
        return result
    except Exception as exc:  # never crash the function on bad input
        return False, [f"could not verify chain: {exc}"]
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)


def _extract_chain_text(raw: bytes) -> str:
    """Pull the chain text out of a request body.

    Accepts both forms: a JSON object ``{"log": "..."}`` (uses the ``log`` value), or
    the raw chain text itself. Anything that is not a JSON object with a ``log`` key is
    treated verbatim as the chain text.
    """
    decoded = raw.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(decoded)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return decoded
    if isinstance(parsed, dict):
        log = parsed.get("log")
        if isinstance(log, str):
            return log
    return decoded


class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("access-control-allow-origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # CORS preflight
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "POST, OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        text = _extract_chain_text(raw)
        ok, problems = verify_payload(text)
        self._send(200, {"ok": ok, "problems": problems})
