"""Vercel Python serverless function: the OPTIONAL live-LLM advisor reply.

This is the cost-capped, engine-gated companion to ``decide.py``. The flow:

1. Normalize the consultation and run the deterministic engine
   (``regrails.guardrail.decide``). **The decision is authoritative.**
2. ONLY ``outcome in {"allow", "out_of_scope"}`` is allowed to call the LLM
   (``regrails.llm.advisor_render``) to phrase the reply. Every other outcome —
   block / escalate_consent / escalate_directory_check / escalate_human_review /
   insufficient_facts — returns a short, warm, accurate TEMPLATED message with
   NO model call. This is the whole thesis (and the cost control): high-stakes,
   irreversible paths never reach a stochastic model, and the cheap default
   model is only ever invoked on the safe, reversible outcomes.
3. Always-degrade: if no API key is present, or ``advisor_render`` raises, or
   anything else goes wrong, return HTTP 200 with the engine decision plus a
   canned/templated reply. The page must never break.

The API key is read ONLY from ``os.environ.get("OPENROUTER_API_KEY")`` (see
``do_POST``). It is never hardcoded, never logged, and never echoed back in the
response body. If absent, the endpoint still works — it just degrades to the
templated reply. Synthetic demo data only.

Cost note: the real cost controls are (a) the engine gate above and (b) the
cheap default model in ``advisor_render`` (``anthropic/claude-3.5-haiku``). The
in-instance rate limiter below is best-effort only — Vercel runs many isolated
instances, so a true cross-instance cap would need Vercel KV / Upstash. The
optional ``REPLY_DAILY_CAP`` env var documents the intent without pretending to
be a hard global cap.
"""

from __future__ import annotations

import json
import os
import time
from http.server import BaseHTTPRequestHandler
from typing import Any

# Engine + renderer are imported at MODULE TOP (not lazily inside the handler):
# the live-reply path always needs them, and importing ``advisor_render`` here
# is what lets callers/tests patch ``reply.advisor_render`` to mock the model.
from regrails.encode import load_all_rules
from regrails.guardrail import ConsultationRequest, decide
from regrails.llm import advisor_render

# Rules are loaded once per warm instance (mirrors decide.py's caching).
_RULES: Any = None

# Outcomes the deterministic engine deems safe + reversible enough to let a
# stochastic model phrase the reply. EVERYTHING else is templated (no LLM).
_LLM_ELIGIBLE_OUTCOMES = frozenset({"allow", "out_of_scope"})

# Templated, model-free replies for every NON-LLM outcome. Wording follows the
# per-outcome intent of ``regrails.llm._ADVISOR_SYSTEM_PROMPT`` so the canned
# text matches what the model would have been instructed to say — but stays
# deterministic, never invents facts, and never answers a gated question.
_TEMPLATED: dict[str, str] = {
    "block": (
        "I can't help with this request — the records-disclosure rules don't permit it. "
        "Please see the specific section numbers listed in the decision for the exact basis, "
        "and ask the registrar about getting written consent or using a permitted exception "
        "if the disclosure is genuinely needed."
    ),
    "escalate_consent": (
        "I can't answer this one yet, because it first needs the right written consent or "
        "contractual condition on file. Please work with the registrar to put the required "
        "signed consent or vendor/study agreement in place, then this can be revisited."
    ),
    "escalate_directory_check": (
        "Before I can share anything here, the student's directory-information opt-out status "
        "has to be confirmed with the registrar. Please verify the student has not opted out "
        "first; if they have, we'd need their written consent instead."
    ),
    "escalate_human_review": (
        "This is a high-stakes financial-aid determination that a human aid officer needs to "
        "make — I'm not able to decide it for you, and I don't want to give you a number that "
        "later turns out to be wrong. Please contact your institution's financial-aid office; "
        "they can review your specific situation and walk you through your options."
    ),
    "insufficient_facts": (
        "I can't assess this yet — some key facts are missing before anyone can answer it "
        "accurately. Please gather the specific details noted in the decision (for example "
        "your satisfactory-academic-progress result and loan-default status), or reach out to "
        "the financial-aid office, and this can be picked back up."
    ),
}

# Warm, accurate fallback used for an LLM-ELIGIBLE outcome when the model can't
# run (no key / render error). We don't fabricate a regulatory answer; we defer
# to the engine's own deterministic guidance and point the user at a human.
_DEGRADED_ALLOW_REPLY = (
    "Here's the guidance from the rules engine for your question (the live assistant isn't "
    "available right now, so this is the deterministic summary). If anything is unclear, your "
    "institution's advising or financial-aid office can confirm the specifics for your situation."
)

# ---------------------------------------------------------------------------
# Best-effort in-instance rate limiter (NOT a real cross-instance cap).
# ---------------------------------------------------------------------------
_CALL_TIMESTAMPS: list[float] = []
_RATE_WINDOW_SECONDS = 86_400.0  # 24h rolling window


def _reply_daily_cap() -> int | None:
    """Read the optional ``REPLY_DAILY_CAP`` env var; ``None`` = uncapped.

    This caps LLM calls *within a single warm instance only*. Vercel fans
    requests across many isolated instances, so this cannot enforce a true
    global daily budget — that would require shared state (Vercel KV / Upstash).
    The durable cost controls are the engine gate + the cheap default model.
    """
    raw = os.environ.get("REPLY_DAILY_CAP")
    if not raw:
        return None
    try:
        cap = int(raw)
    except ValueError:
        return None
    return cap if cap > 0 else None


def _rate_limited() -> bool:
    """Return True if this warm instance has hit its best-effort LLM cap."""
    cap = _reply_daily_cap()
    if cap is None:
        return False
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SECONDS
    # Drop timestamps outside the rolling window (in place).
    _CALL_TIMESTAMPS[:] = [t for t in _CALL_TIMESTAMPS if t >= cutoff]
    return len(_CALL_TIMESTAMPS) >= cap


def _normalize_consultation(data: dict[str, Any]) -> dict[str, Any]:
    """Mirror ``decide.py``'s normalizer: drop None/"" and split a CSV string."""
    cons = {k: v for k, v in (data or {}).items() if v is not None and v != ""}
    cons.setdefault("query", "")
    if isinstance(cons.get("data_requested"), str):
        cons["data_requested"] = [s.strip() for s in cons["data_requested"].split(",") if s.strip()]
    return cons


def reply_payload(data: dict[str, Any], *, api_key: str | None) -> tuple[int, dict[str, Any]]:
    """Normalize -> decide -> branch (LLM vs templated) -> build the response.

    Returns ``(http_status, body)`` where ``body`` is
    ``{"decision": <decision json>, "guarded_reply": str, "model_used": str | None}``.

    Always returns HTTP 200 once the engine has produced a decision — the page
    must never break. The only non-200 path is a malformed consultation shape
    (mirrors ``decide.py``'s 400), which still returns structured JSON.
    """
    global _RULES
    if _RULES is None:
        _RULES = load_all_rules()

    cons = _normalize_consultation(data)
    try:
        req = ConsultationRequest(**cons)
    except Exception as exc:  # invalid enum / shape -> 400, not a crash
        return 400, {"error": f"invalid consultation: {exc}"}

    decision = decide(req, _RULES)
    decision_json = decision.model_dump(mode="json")
    outcome = decision.outcome

    # --- Engine gate: only safe/reversible outcomes may reach the model. -----
    if outcome not in _LLM_ELIGIBLE_OUTCOMES:
        return 200, {
            "decision": decision_json,
            "guarded_reply": _TEMPLATED[outcome],
            "model_used": None,
        }

    # LLM-eligible, but degrade if there's no key or we've hit the soft cap.
    if not api_key or _rate_limited():
        return 200, {
            "decision": decision_json,
            "guarded_reply": _DEGRADED_ALLOW_REPLY,
            "model_used": None,
        }

    # Try the (cheap) model; any failure degrades to the templated reply.
    try:
        text, model_used = advisor_render(query=req.query, decision=decision, api_key=api_key)
        _CALL_TIMESTAMPS.append(time.monotonic())
    except Exception:  # provider down / timeout / empty content -> never break the page
        return 200, {
            "decision": decision_json,
            "guarded_reply": _DEGRADED_ALLOW_REPLY,
            "model_used": None,
        }

    reply_text = text if text.strip() else _DEGRADED_ALLOW_REPLY
    return 200, {
        "decision": decision_json,
        "guarded_reply": reply_text,
        "model_used": model_used,
    }


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
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON body"})
            return
        # The API key is read ONLY here, straight from the environment — never
        # hardcoded, never logged, never returned in the response.
        code, obj = reply_payload(data, api_key=os.environ.get("OPENROUTER_API_KEY"))
        self._send(code, obj)
