"""Vercel Python serverless function: run the deterministic guardrail (no LLM).

POST a JSON consultation (``query`` + optional structured fields) and get back the
typed ``GuardrailDecision``. Engine-only — no LLM, no API key. Synthetic data only.
The engine is the published ``regrails`` package (see requirements.txt).
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler
from typing import Any

# The consultation normalizer is shared with ``reply.py`` (single source of truth
# in the ``regrails`` package) so the two endpoints can never drift — see the
# ``regrails.guardrail.normalize_consultation`` docstring.
from regrails.guardrail import normalize_consultation

# Reject request bodies larger than this BEFORE reading them (security L-1). A
# consultation is a small JSON object; 64 KiB is generous headroom.
MAX_BODY = 64 * 1024

_RULES: Any = None


def decide_payload(data: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Run the engine on a consultation dict. Returns (http_status, body)."""
    from regrails.encode import load_all_rules
    from regrails.guardrail import ConsultationRequest, decide

    global _RULES
    if _RULES is None:
        _RULES = load_all_rules()

    cons = normalize_consultation(data)
    try:
        req = ConsultationRequest(**cons)
    except Exception as exc:  # invalid enum / shape -> 400, not a crash
        return 400, {"error": f"invalid consultation: {exc}"}
    return 200, decide(req, _RULES).model_dump(mode="json")


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
        # Reject an oversized body up front, BEFORE reading it (security L-1).
        if length > MAX_BODY:
            self._send(413, {"error": "request body too large"})
            return
        # Defense-in-depth: never read more than MAX_BODY bytes even if the
        # declared length is in-range (a client could still over-send).
        raw = self.rfile.read(min(length, MAX_BODY)) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid JSON body"})
            return
        code, obj = decide_payload(data)
        self._send(code, obj)
