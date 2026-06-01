"""v0.2 guardrail unit tests — Title IV cascade, new outcomes, risk tiering.

The golden corpus (test_golden.py) is the broad behavioral contract; these are
focused unit assertions on the v0.2 additions.
"""

from __future__ import annotations

import pytest

from regrails.encode import load_all_rules
from regrails.guardrail import ConsultationRequest, _risk_for, decide, derive_tags
from regrails.models import Rule


@pytest.fixture(scope="module")
def rules() -> list[Rule]:
    return load_all_rules()


class TestOutOfScope:
    def test_topic_other_is_out_of_scope(self, rules: list[Rule]) -> None:
        d = decide(ConsultationRequest(query="Library hours?", topic="other"), rules)
        assert d.outcome == "out_of_scope"
        assert d.risk_tier == "low"
        assert d.human_gate_required is False
        assert d.matched_rules == []
        assert d.framework == "n/a"

    def test_derive_tags_other_empty(self) -> None:
        assert derive_tags(ConsultationRequest(query="x", topic="other")) == set()


class TestTitleIVCascade:
    def test_default_is_high_gate(self, rules: list[Rule]) -> None:
        d = decide(
            ConsultationRequest(
                query="defaulted, eligible?", topic="aid_status",
                aid_determination_requested=True, student_in_default=True,
            ),
            rules,
        )
        assert d.outcome == "escalate_human_review"
        assert d.risk_tier == "high"
        assert d.human_gate_required is True
        assert any("668.32(g)(1)" in c for c in d.citations_emitted)

    def test_failed_sap_determination_is_high_gate(self, rules: list[Rule]) -> None:
        d = decide(
            ConsultationRequest(
                query="failed SAP, keep aid?", topic="aid_status",
                sap_status="failed_eval", aid_determination_requested=True,
            ),
            rules,
        )
        assert d.outcome == "escalate_human_review"
        assert d.human_gate_required is True

    def test_unknown_facts_is_insufficient(self, rules: list[Rule]) -> None:
        d = decide(
            ConsultationRequest(
                query="will I get aid?", topic="aid_status", aid_determination_requested=True,
            ),
            rules,
        )
        assert d.outcome == "insufficient_facts"
        assert d.human_gate_required is False

    def test_warning_is_informational_allow(self, rules: list[Rule]) -> None:
        d = decide(
            ConsultationRequest(query="warning?", topic="aid_status", sap_status="on_warning"),
            rules,
        )
        assert d.outcome == "allow"
        assert d.risk_tier == "medium"

    def test_aid_status_tags_disjoint_from_ferpa(self) -> None:
        tags = derive_tags(ConsultationRequest(query="x", topic="aid_status"))
        assert "pii_request" not in tags
        assert "default_consent_gate" not in tags
        assert "aid_eligibility" in tags


class TestRiskMapping:
    @pytest.mark.parametrize(
        ("outcome", "framework", "citations", "expected"),
        [
            ("escalate_human_review", "Title IV", [], ("high", True)),
            ("block", "FERPA", [], ("medium", False)),
            ("escalate_consent", "FERPA", [], ("medium", False)),
            ("insufficient_facts", "Title IV", [], ("low", False)),
            ("out_of_scope", "n/a", [], ("low", False)),
            ("allow", "FERPA", ["34-CFR-99.36"], ("medium", False)),
            ("allow", "FERPA", ["34-CFR-99.31(b)(1)"], ("low", False)),
            ("allow", "Title IV", ["34-CFR-668.34"], ("medium", False)),
        ],
    )
    def test_risk_for(
        self,
        outcome: str,
        framework: str,
        citations: list[str],
        expected: tuple[str, bool],
    ) -> None:
        assert _risk_for(outcome, framework, citations) == expected  # type: ignore[arg-type]


class TestDecisionFields:
    def test_decision_carries_v2_fields(self, rules: list[Rule]) -> None:
        d = decide(ConsultationRequest(query="x", data_requested=["gpa"]), rules)
        assert d.framework == "FERPA"
        assert d.risk_tier in ("low", "medium", "high")
        assert isinstance(d.human_gate_required, bool)
