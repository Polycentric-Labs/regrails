"""Unit tests for the shared ``regrails.guardrail.normalize_consultation`` helper.

Both Vercel endpoints (``web/api/decide.py`` and ``web/api/reply.py``) used to
carry their own copy of the consultation normalizer (drop ``None``/``""`` values,
default ``query`` to ``""``, and CSV-split a string ``data_requested``). That
duplication is the subject of review finding #5. The logic now lives ONCE in the
``regrails`` package and is imported by both endpoints; these tests pin its
behavior against a table of inputs so the two endpoints can never diverge.
"""

from __future__ import annotations

from typing import Any

import pytest

from regrails.guardrail import normalize_consultation

# (input, expected_output) table. Each row exercises one normalization rule.
_CASES: list[tuple[dict[str, Any], dict[str, Any]]] = [
    # Empty input -> just the defaulted query.
    ({}, {"query": ""}),
    # None input behaves like empty input (defensive: callers may pass a parsed null).
    # (handled by the dedicated None test below, since dict typing can't express it)
    # None / "" values are dropped; the surviving query is kept.
    (
        {"query": "hi", "topic": None, "requester_role": ""},
        {"query": "hi"},
    ),
    # A missing query is defaulted to "".
    ({"topic": "disclosure"}, {"query": "", "topic": "disclosure"}),
    # A CSV string data_requested is split + stripped; empty fragments dropped.
    (
        {"query": "q", "data_requested": "gpa, grades ,, transcript"},
        {"query": "q", "data_requested": ["gpa", "grades", "transcript"]},
    ),
    # A single-item CSV string still becomes a one-element list.
    (
        {"query": "q", "data_requested": "transcript"},
        {"query": "q", "data_requested": ["transcript"]},
    ),
    # An already-list data_requested is passed through untouched (not re-split).
    (
        {"query": "q", "data_requested": ["gpa", "grades"]},
        {"query": "q", "data_requested": ["gpa", "grades"]},
    ),
    # An empty-string data_requested is dropped entirely (falls to the field default).
    ({"query": "q", "data_requested": ""}, {"query": "q"}),
    # False booleans are KEPT (False is not None and not "") — important for FERPA facts.
    (
        {"query": "q", "consent_on_file": False},
        {"query": "q", "consent_on_file": False},
    ),
    # Zero is kept (0 is not None and not "").
    ({"query": "q", "count": 0}, {"query": "q", "count": 0}),
]


@pytest.mark.parametrize(("data", "expected"), _CASES)
def test_normalize_consultation_table(data: dict[str, Any], expected: dict[str, Any]) -> None:
    assert normalize_consultation(data) == expected


def test_normalize_consultation_none_input() -> None:
    """A ``None`` body normalizes to the same shape as an empty dict."""
    assert normalize_consultation(None) == {"query": ""}  # type: ignore[arg-type]


def test_normalize_consultation_does_not_mutate_input() -> None:
    """The helper must not mutate its argument (the endpoints reuse the dict)."""
    src = {"query": "q", "data_requested": "gpa, grades", "topic": None}
    snapshot = dict(src)
    normalize_consultation(src)
    assert src == snapshot


def test_both_endpoints_use_the_shared_helper() -> None:
    """Regression for finding #5: decide.py and reply.py must produce identical
    normalized output for the same input (they import the one shared helper)."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "api"))
    import decide  # noqa: PLC0415
    import reply  # noqa: PLC0415

    for data, _expected in _CASES:
        assert decide.normalize_consultation(data) == reply.normalize_consultation(data)
        assert decide.normalize_consultation(data) == normalize_consultation(data)
