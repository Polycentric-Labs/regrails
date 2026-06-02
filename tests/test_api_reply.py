"""Tests for the ``/api/reply`` Vercel function (``web/api/reply.py``).

The whole thesis of ``reply.py`` is the **engine gate**: the deterministic
``regrails.guardrail.decide`` runs first and is authoritative, and ONLY the
``allow`` / ``out_of_scope`` outcomes are allowed to reach the LLM. Every
high-stakes path (block / the escalations / insufficient_facts) returns a
templated message and never touches the model — which both caps cost and
guarantees irreversible determinations are never phrased by a stochastic model.

These tests MOCK ``advisor_render`` — they never hit a live API, so they pass
in CI (which runs ``-m "not live"``). The single optional live test is marked
and excluded from the default run.

The path shim below mirrors ``web/api/decide.py``'s deployment layout: on
Vercel each file in ``web/api/`` is its own function, so the test imports
``reply`` directly off ``web/api`` rather than as a package.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "api"))

from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
import reply  # noqa: E402

# A high-stakes Title IV consultation: a student in default asking whether they
# remain aid-eligible. The engine maps this to ``escalate_human_review`` (the
# one outcome that sets human_gate_required=True). This MUST NOT call the model.
_HIGH_STAKES = {
    "query": "I defaulted on my federal loan last year — can I still get aid?",
    "topic": "aid_status",
    "aid_determination_requested": True,
    "student_in_default": True,
}

# A plain, non-regulated question -> ``out_of_scope`` (an LLM-eligible outcome).
_OUT_OF_SCOPE = {"query": "What time does the library close on Fridays?", "topic": "other"}


def test_high_stakes_never_calls_llm() -> None:
    """escalate_human_review must return templated text WITHOUT touching the LLM."""
    with patch.object(reply, "advisor_render") as mock_render:
        status, body = reply.reply_payload(_HIGH_STAKES, api_key="sk-fake-present")

    mock_render.assert_not_called()
    assert status == 200
    assert body["decision"]["outcome"] == "escalate_human_review"
    assert body["decision"]["human_gate_required"] is True
    assert isinstance(body["guarded_reply"], str)
    assert body["guarded_reply"].strip()  # non-empty templated text
    assert body["model_used"] is None


def test_allow_renders_when_key_present() -> None:
    """An LLM-eligible outcome with a key present uses advisor_render's output verbatim."""
    rendered = ("The library closes at 9pm on Fridays. Have a good evening!", "test-model")
    with patch.object(reply, "advisor_render", return_value=rendered) as mock_render:
        status, body = reply.reply_payload(_OUT_OF_SCOPE, api_key="sk-fake-present")

    mock_render.assert_called_once()
    # The API key must be forwarded to the renderer (and only ever come from env upstream).
    assert mock_render.call_args.kwargs.get("api_key") == "sk-fake-present"
    assert status == 200
    assert body["decision"]["outcome"] == "out_of_scope"
    assert body["guarded_reply"] == rendered[0]
    assert body["model_used"] == rendered[1]


def test_missing_key_degrades() -> None:
    """No api_key -> templated reply, no LLM call, still HTTP 200 (page never breaks)."""
    with patch.object(reply, "advisor_render") as mock_render:
        status, body = reply.reply_payload(_OUT_OF_SCOPE, api_key=None)

    mock_render.assert_not_called()
    assert status == 200
    assert body["decision"]["outcome"] == "out_of_scope"
    assert isinstance(body["guarded_reply"], str)
    assert body["guarded_reply"].strip()
    assert body["model_used"] is None


def test_llm_failure_degrades_to_template() -> None:
    """If advisor_render raises, the endpoint still returns 200 with a templated reply."""
    with patch.object(reply, "advisor_render", side_effect=RuntimeError("provider down")):
        status, body = reply.reply_payload(_OUT_OF_SCOPE, api_key="sk-fake-present")

    assert status == 200
    assert body["decision"]["outcome"] == "out_of_scope"
    assert body["guarded_reply"].strip()  # fell back to canned text
    assert body["model_used"] is None


def test_block_outcome_is_templated_and_cites_sections() -> None:
    """A block path returns templated text that points at section numbers, no LLM."""
    block_req = {
        "query": "Forward this student's full transcript to my buddy at another school.",
        "topic": "disclosure",
        "requester_role": "third_party",
        "data_requested": "transcript",
        "receiver_redisclosing": True,
    }
    with patch.object(reply, "advisor_render") as mock_render:
        status, body = reply.reply_payload(block_req, api_key="sk-fake-present")

    mock_render.assert_not_called()
    assert status == 200
    assert body["decision"]["outcome"] == "block"
    assert body["model_used"] is None
    # The templated block message should steer the user to the cited section numbers.
    assert "section" in body["guarded_reply"].lower()


def test_every_non_llm_outcome_has_a_template() -> None:
    """Defensive: each non-LLM outcome maps to a non-empty templated message."""
    for outcome in (
        "block",
        "escalate_consent",
        "escalate_directory_check",
        "escalate_human_review",
        "insufficient_facts",
    ):
        assert reply._TEMPLATED[outcome].strip()


@pytest.mark.live
def test_live_render_smoke() -> None:  # pragma: no cover - excluded from CI (-m "not live")
    """Optional: only runs with a real OPENROUTER_API_KEY; excluded from the default run."""
    import os

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("no OPENROUTER_API_KEY in env")
    status, body = reply.reply_payload(_OUT_OF_SCOPE, api_key=key)
    assert status == 200
    assert body["guarded_reply"].strip()
    assert body["model_used"]  # a real model id came back
