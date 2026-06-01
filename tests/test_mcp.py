"""Tests for the MCP tool functions (called directly — no socket, no LLM)."""

from __future__ import annotations

from regrails.mcp_server import check_faithfulness, consult_guardrail, list_rules


def test_consult_default_block() -> None:
    d = consult_guardrail(query="What's Jane Doe's GPA?", data_requested=["gpa"])
    assert d["outcome"] == "block"
    assert d["framework"] == "FERPA"
    assert d["human_gate_required"] is False


def test_consult_title_iv_human_gate() -> None:
    d = consult_guardrail(
        query="I defaulted on a loan; am I still eligible?",
        topic="aid_status",
        aid_determination_requested=True,
        student_in_default=True,
    )
    assert d["outcome"] == "escalate_human_review"
    assert d["risk_tier"] == "high"
    assert d["human_gate_required"] is True
    assert any("668.32(g)(1)" in c for c in d["citations_emitted"])


def test_consult_out_of_scope() -> None:
    d = consult_guardrail(query="What time does the library close?", topic="other")
    assert d["outcome"] == "out_of_scope"


def test_list_rules_all() -> None:
    assert len(list_rules()) == 37


def test_list_rules_title_iv() -> None:
    rs = list_rules(framework="Title IV")
    assert len(rs) == 14
    assert all(r["framework"] == "Title IV" for r in rs)


def test_check_faithfulness() -> None:
    assert check_faithfulness() == {"passed": 37, "total": 37}
