"""Tests for the SARIF 2.1.0 export."""

from __future__ import annotations

from typing import Any

from regrails.encode import load_all_rules
from regrails.guardrail import ConsultationRequest, decide
from regrails.sarif import decision_to_result, to_sarif

RULES = load_all_rules()


def _decide(**kw: Any):  # type: ignore[no-untyped-def]
    return decide(ConsultationRequest(**kw), RULES)


def test_sarif_version_and_driver() -> None:
    s = to_sarif([_decide(query="x", data_requested=["gpa"])])
    assert s["version"] == "2.1.0"
    assert s["runs"][0]["tool"]["driver"]["name"] == "RegRails"
    assert len(s["runs"][0]["results"]) == 1


def test_block_is_error_with_cfr_ruleid() -> None:
    r = decision_to_result(_decide(query="What's the GPA?", data_requested=["gpa"]))
    assert r["level"] == "error"
    assert r["ruleId"].startswith("34-CFR-")


def test_human_review_is_error_and_flags_gate() -> None:
    r = decision_to_result(
        _decide(
            query="defaulted; eligible?",
            topic="aid_status",
            aid_determination_requested=True,
            student_in_default=True,
        )
    )
    assert r["level"] == "error"
    assert r["properties"]["human_gate_required"] is True


def test_allow_is_level_none() -> None:
    r = decision_to_result(_decide(query="warning meaning?", topic="aid_status", sap_status="on_warning"))
    assert r["level"] == "none"


def test_out_of_scope_empty_citations_falls_back_to_framework() -> None:
    r = decision_to_result(_decide(query="library hours?", topic="other"))
    assert r["ruleId"]  # non-empty (framework fallback)
