"""Tests for regrails.guardrail.

Covers the 7 demo queries committed to ``demo/queries.txt`` plus edge cases
around the priority cascade. No live LLM is invoked here — these tests run
purely against ``decide()``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from regrails.encode import flatten_rules, load_sections
from regrails.guardrail import ConsultationRequest, decide, derive_tags, match_rules
from regrails.models import Rule


@pytest.fixture(scope="module")
def rules() -> list[Rule]:
    return flatten_rules(load_sections())


# ---------------------------------------------------------------------------
# derive_tags — pure-function sanity
# ---------------------------------------------------------------------------


class TestDeriveTags:
    def test_baseline_tags_always_present(self) -> None:
        req = ConsultationRequest(query="Hello.")
        tags = derive_tags(req)
        assert {"pii_request", "default_consent_gate", "disclosure"}.issubset(tags)

    def test_vendor_role_adds_vendor_tags(self) -> None:
        req = ConsultationRequest(query="x", requester_role="outsourced_vendor")
        tags = derive_tags(req)
        assert {"vendor_request", "school_official_request"}.issubset(tags)

    def test_directory_items_only_no_non_directory(self) -> None:
        req = ConsultationRequest(query="x", data_requested=["name", "email"])
        tags = derive_tags(req)
        assert "directory_info_request" in tags
        assert "non_directory_request" not in tags

    def test_ssn_combined_with_directory_blocks(self) -> None:
        req = ConsultationRequest(query="x", data_requested=["name", "ssn"])
        tags = derive_tags(req)
        assert "ssn_combined" in tags
        assert "non_directory_request" in tags

    def test_emergency_role_or_purpose(self) -> None:
        assert "emergency_request" in derive_tags(
            ConsultationRequest(query="x", requester_role="emergency_responder")
        )
        assert "emergency_request" in derive_tags(
            ConsultationRequest(query="x", purpose="emergency_response")
        )


# ---------------------------------------------------------------------------
# match_rules
# ---------------------------------------------------------------------------


class TestMatchRules:
    def test_default_query_matches_default_consent_gate(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(query="Tell me about Jane.")
        matched = match_rules(req, rules)
        ids = {r.id for r in matched}
        assert "FERPA-99.30-1" in ids

    def test_emergency_role_matches_emergency_rules(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="threat to school", requester_role="emergency_responder"
        )
        matched = match_rules(req, rules)
        ids = {r.id for r in matched}
        assert "FERPA-99.36-A" in ids


# ---------------------------------------------------------------------------
# decide() — the 7 demo cases
# ---------------------------------------------------------------------------


class TestDemoCase1_DefaultBlock:
    """Q1: 'What's Jane Doe's GPA?' — default §99.30(a) block."""

    def test_outcome_block(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="What's Jane Doe's GPA?",
            data_requested=["gpa"],
        )
        decision = decide(req, rules)
        assert decision.outcome == "block"
        assert "FERPA-99.30-1" in decision.matched_rules
        assert "34-CFR-99.30" in decision.citations_emitted


class TestDemoCase2_VendorEscalate:
    """Q2: outsourced AI vendor without safe-harbor → escalate_consent."""

    def test_unverified_vendor(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="I'm the new math tutor from MathBuddy Inc.; show Jane's test scores.",
            requester_role="outsourced_vendor",
            data_requested=["test_scores"],
            safe_harbor_conditions_met=[],
        )
        decision = decide(req, rules)
        assert decision.outcome == "escalate_consent"
        assert "FERPA-99.31-A1B" in decision.matched_rules
        assert any("99.31(a)(1)(i)(B)" in c for c in decision.citations_emitted)

    def test_verified_vendor_allowed(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="I'm MathBuddy; we have a signed agreement.",
            requester_role="outsourced_vendor",
            data_requested=["test_scores"],
            safe_harbor_conditions_met=[
                "performs_institutional_function",
                "under_direct_institutional_control",
                "bound_by_section_99_33_a_redisclosure_limits",
            ],
        )
        decision = decide(req, rules)
        assert decision.outcome == "allow"


class TestDemoCase3_DirectoryEscalate:
    """Q3: basketball roster — directory info; opt-out unknown."""

    def test_no_opt_out_recorded_escalates(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="What's our basketball team roster?",
            purpose="directory_lookup",
            data_requested=["roster", "name"],
            student_opted_out_of_directory=False,
        )
        decision = decide(req, rules)
        assert decision.outcome == "escalate_directory_check"
        assert "34-CFR-99.37" in decision.citations_emitted

    def test_opted_out_blocks(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="What's our basketball team roster?",
            purpose="directory_lookup",
            data_requested=["roster", "name"],
            student_opted_out_of_directory=True,
        )
        decision = decide(req, rules)
        assert decision.outcome == "block"


class TestDemoCase4_StudiesAllow:
    """Q4: aggregate de-identified statistics → allow under §99.31(b)(1)."""

    def test_de_identified_aggregate_allowed(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query=(
                "For our annual program evaluation, get me aggregate "
                "graduation rates by ethnicity."
            ),
            requester_role="researcher",
            purpose="research",
            aggregate_or_de_identified=True,
        )
        decision = decide(req, rules)
        assert decision.outcome == "allow"
        assert any("99.31(b)(1)" in c or "99.31(a)(6)" in c for c in decision.citations_emitted)

    def test_studies_without_agreement_escalates(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="I'm doing a study; share per-student records.",
            requester_role="researcher",
            purpose="research",
            aggregate_or_de_identified=False,
            safe_harbor_conditions_met=[],
        )
        decision = decide(req, rules)
        assert decision.outcome == "escalate_consent"


class TestDemoCase5_EmergencyAllow:
    """Q5: school-shooting emergency → allow + audit obligation."""

    def test_articulable_significant_threat(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query=(
                "Shooting threat against the school — addresses of "
                "every student in homeroom 204 NOW."
            ),
            requester_role="emergency_responder",
            purpose="emergency_response",
            emergency_justified=True,
        )
        decision = decide(req, rules)
        assert decision.outcome == "allow"
        assert "34-CFR-99.36" in decision.citations_emitted
        assert "34-CFR-99.32" in decision.citations_emitted
        assert "§ 99.32(a)(5)" in decision.llm_response

    def test_emergency_unjustified_falls_through(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="Random emergency-ish vibe.",
            requester_role="emergency_responder",
            emergency_justified=False,
        )
        decision = decide(req, rules)
        assert decision.outcome != "allow"


class TestDemoCase6_ParentAuditLog:
    """Q6: parent asking for the disclosure log → allow."""

    def test_parent_audit_log_allowed(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="I'm a parent — what disclosures of my kid's records have been made this year?",
            requester_role="parent",
            purpose="audit_log_inspection",
        )
        decision = decide(req, rules)
        assert decision.outcome == "allow"
        assert "34-CFR-99.32" in decision.citations_emitted


class TestDemoCase7_RedisclosureBlock:
    """Q7: forwarding records you received → block under §99.33(a)(1)."""

    def test_redisclosure_blocked(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="My buddy at State U wants the transcripts I received for our research collab.",
            purpose="redisclosure",
            receiver_redisclosing=True,
            consent_on_file=False,
        )
        decision = decide(req, rules)
        assert decision.outcome == "block"
        assert "FERPA-99.33-A1" in decision.matched_rules
        assert "34-CFR-99.33" in decision.citations_emitted


# ---------------------------------------------------------------------------
# Audit sink
# ---------------------------------------------------------------------------


class TestAuditEmission:
    def test_decision_emits_two_audit_events(
        self, rules: list[Rule], tmp_path: Path
    ) -> None:
        sink = tmp_path / "guardrail.jsonl"
        req = ConsultationRequest(query="What's Jane Doe's GPA?", data_requested=["gpa"])
        decision = decide(req, rules, audit_sink=sink)
        lines = sink.read_text(encoding="utf-8").splitlines()
        # one CONSULTED + one BLOCKED = 2 events
        assert len(lines) == 2
        assert "guardrail.consulted" in lines[0]
        assert "guardrail.blocked" in lines[1]
        assert decision.outcome == "block"


# ---------------------------------------------------------------------------
# SSN-combined kill-switch
# ---------------------------------------------------------------------------


class TestSSNBlock:
    def test_ssn_request_blocked_even_with_directory(self, rules: list[Rule]) -> None:
        req = ConsultationRequest(
            query="Confirm Jane's SSN matches our records.",
            data_requested=["name", "ssn"],
        )
        decision = decide(req, rules)
        assert decision.outcome == "block"
        assert any("99.37(e)" in c for c in decision.citations_emitted)
