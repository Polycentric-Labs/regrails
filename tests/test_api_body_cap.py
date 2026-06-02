"""Request-body size-cap tests for the three Vercel endpoints (security L-1).

Each ``do_POST`` must reject an oversized body BEFORE reading it: if the
``content-length`` header exceeds ``MAX_BODY`` (64 KiB) the handler returns
HTTP 413 ``{"error": "request body too large"}`` and reads at most ``MAX_BODY``
bytes off the wire. ``reply.py`` additionally clamps an over-long ``query`` to
``MAX_QUERY`` (8 KiB) before it can reach ``advisor_render`` (bounds LLM spend).

``BaseHTTPRequestHandler`` normally needs a live socket; these tests drive
``do_POST`` directly on a handler instance built with ``__new__`` (bypassing the
socket-bound ``__init__``) and hand it fake ``headers`` / ``rfile`` / ``wfile``.
"""

from __future__ import annotations

import io
import json
import sys
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "api"))

import decide  # noqa: E402
import reply  # noqa: E402
import verify  # noqa: E402


class _CountingReader(io.BytesIO):
    """A BytesIO that records the largest ``read(n)`` it was asked for."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.max_requested: int | None = None

    def read(self, size: int | None = -1, /) -> bytes:
        if size is not None and size >= 0:
            self.max_requested = max(self.max_requested or 0, size)
        return super().read(size)


def _headers(content_length: int) -> Message:
    msg = Message()
    msg["content-length"] = str(content_length)
    return msg


def _drive_post(module: Any, body: bytes, *, declared_length: int | None = None) -> tuple[int, Any]:
    """Invoke ``module.handler.do_POST`` with a fake request and capture the response.

    ``declared_length`` lets a test LIE about content-length (claim a huge body
    while sending a small one) to prove the pre-read header check fires.
    """
    h = module.handler.__new__(module.handler)  # bypass socket-bound __init__
    length = declared_length if declared_length is not None else len(body)
    h.headers = _headers(length)
    reader = _CountingReader(body)
    h.rfile = reader
    h.wfile = io.BytesIO()

    captured: dict[str, Any] = {}

    def fake_send(code: int, obj: dict[str, Any]) -> None:
        captured["code"] = code
        captured["obj"] = obj

    # Patch the bound _send so we don't need send_response/end_headers machinery.
    with patch.object(h, "_send", side_effect=fake_send):
        h.do_POST()

    captured["max_read"] = reader.max_requested
    return captured["code"], captured


# ---------------------------------------------------------------------------
# Oversized-body rejection (all three endpoints)
# ---------------------------------------------------------------------------


def test_decide_rejects_oversized_content_length() -> None:
    code, cap = _drive_post(decide, b"{}", declared_length=decide.MAX_BODY + 1)
    assert code == 413
    assert cap["obj"] == {"error": "request body too large"}


def test_reply_rejects_oversized_content_length() -> None:
    code, cap = _drive_post(reply, b"{}", declared_length=reply.MAX_BODY + 1)
    assert code == 413
    assert cap["obj"] == {"error": "request body too large"}


def test_verify_rejects_oversized_content_length() -> None:
    code, cap = _drive_post(verify, b"x", declared_length=verify.MAX_BODY + 1)
    assert code == 413
    assert cap["obj"] == {"error": "request body too large"}


def test_max_body_constant_is_64k() -> None:
    assert decide.MAX_BODY == 64 * 1024
    assert reply.MAX_BODY == 64 * 1024
    assert verify.MAX_BODY == 64 * 1024


# ---------------------------------------------------------------------------
# Bounded read: never read more than MAX_BODY bytes off the wire
# ---------------------------------------------------------------------------


def test_decide_reads_at_most_max_body() -> None:
    # An honest, in-range request still succeeds and never asks for > MAX_BODY.
    body = json.dumps({"query": "hi", "topic": "other"}).encode("utf-8")
    code, cap = _drive_post(decide, body)
    assert code == 200
    assert cap["max_read"] is not None
    assert cap["max_read"] <= decide.MAX_BODY


def test_verify_caps_read_when_length_header_is_in_range() -> None:
    # content-length within the cap: the handler must not read more than MAX_BODY.
    body = b"not-a-chain"
    code, cap = _drive_post(verify, body)
    assert code == 200  # verify always returns 200 with a verdict
    assert cap["max_read"] is not None
    assert cap["max_read"] <= verify.MAX_BODY


# ---------------------------------------------------------------------------
# reply.py query clamp (bounds LLM token spend) — security L-1, reply addendum
# ---------------------------------------------------------------------------


def test_reply_clamps_long_query_before_advisor_render() -> None:
    """An LLM-eligible outcome with a giant query must hand advisor_render a query
    no longer than MAX_QUERY (the engine still sees the full text; only the
    LLM-bound copy is clamped)."""
    long_q = "A" * (reply.MAX_QUERY * 3)
    data = {"query": long_q, "topic": "other"}  # -> out_of_scope (LLM-eligible)
    rendered = ("ok", "test-model")
    with patch.object(reply, "advisor_render", return_value=rendered) as mock_render:
        status, body = reply.reply_payload(data, api_key="sk-fake-present")

    assert status == 200
    mock_render.assert_called_once()
    sent_query = mock_render.call_args.kwargs["query"]
    assert len(sent_query) <= reply.MAX_QUERY


def test_reply_max_query_constant_is_8k() -> None:
    assert reply.MAX_QUERY == 8 * 1024
