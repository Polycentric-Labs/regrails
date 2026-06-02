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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "api"))

from typing import get_args  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402
import reply  # noqa: E402

from regrails.models import Outcome  # noqa: E402

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


def test_daily_cap_degrades_second_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """With REPLY_DAILY_CAP=1, the 2nd LLM-eligible call must degrade to the canned
    reply (model_used is None) — the best-effort in-instance rate limiter.

    We don't sleep: the limiter compares ``time.monotonic()`` against a 24h window,
    so we seed ``_CALL_TIMESTAMPS`` with a synthetic *now* timestamp (well inside the
    window) to represent the first call having already consumed the single slot.
    """
    monkeypatch.setenv("REPLY_DAILY_CAP", "1")
    # Isolate the module-global timestamp list (it persists across calls/tests).
    monkeypatch.setattr(reply, "_CALL_TIMESTAMPS", [], raising=True)

    rendered = ("The library closes at 9pm on Fridays.", "test-model")
    with patch.object(reply, "advisor_render", return_value=rendered) as mock_render:
        # 1st call: under the cap -> renders, and records its own timestamp.
        status1, body1 = reply.reply_payload(_OUT_OF_SCOPE, api_key="sk-fake-present")
        assert status1 == 200
        assert body1["model_used"] == "test-model"
        assert mock_render.call_count == 1
        # The successful render appended a timestamp inside the rolling window.
        assert len(reply._CALL_TIMESTAMPS) == 1
        assert reply._CALL_TIMESTAMPS[0] >= time.monotonic() - reply._RATE_WINDOW_SECONDS

        # 2nd call: cap (1) already consumed -> degrade WITHOUT another LLM call.
        status2, body2 = reply.reply_payload(_OUT_OF_SCOPE, api_key="sk-fake-present")

    assert status2 == 200
    assert body2["decision"]["outcome"] == "out_of_scope"
    assert body2["guarded_reply"].strip()  # canned/degraded text, non-empty
    assert body2["model_used"] is None
    # advisor_render was NOT called the second time (still 1 total).
    assert mock_render.call_count == 1


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
    """Exhaustive (derived from the ``Outcome`` type, not a hardcoded list): every
    possible engine outcome is handled by EXACTLY one path — it is either
    LLM-eligible or it has a templated, model-free reply. If a new ``Outcome`` is
    added to ``regrails.models`` without wiring it into ``reply.py``, this fails.
    """
    all_outcomes = set(get_args(Outcome))
    assert set(reply._TEMPLATED) | reply._LLM_ELIGIBLE_OUTCOMES == all_outcomes
    # The two partitions must not overlap (an outcome is templated XOR LLM-eligible).
    assert set(reply._TEMPLATED).isdisjoint(reply._LLM_ELIGIBLE_OUTCOMES)
    # And every templated message is non-empty.
    for outcome in reply._TEMPLATED:
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
