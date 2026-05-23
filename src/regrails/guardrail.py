"""Guardrail decision engine.

A consultation request (constructed by the LLM advisor before answering the
end-user) is fed to :func:`decide`, which walks the encoded FERPA rules in
priority cascade and emits a typed :class:`~regrails.models.GuardrailDecision`.

Cascade (highest priority first):

1. **Emergency** — § 99.36(a) allow path, with the § 99.32(a)(5)
   recordkeeping obligation surfaced.
2. **Redisclosure** — § 99.33(a)(1) hard block when the requester wants to
   forward records they received elsewhere.
3. **Parent audit-log request** — § 99.32(c)(1) allow.
4. **Directory information** — § 99.37(a) opt-out check is the only branch
   where the guardrail must inspect *student state* (opt-out yes/no);
   § 99.37(e) hard-blocks re-identification flows.
5. **Studies / de-identified** — § 99.31(a)(6) + § 99.31(b)(1) allow path
   when conditions are met.
6. **Vendor / outsourced school official** — § 99.31(a)(1)(i)(B) safe-harbor
   verification (escalate when conditions unverified).
7. **Financial aid (Title IV)** — § 99.31(a)(4) allow path for
   eligibility / amount / conditions / enforcement purposes.
8. **Consent on file** — § 99.30 allow path.
9. **Default** — § 99.30(a) block.

The :class:`ConsultationRequest` schema is the LLM-facing contract. Field
shapes are conservative on purpose — every field is optional with a safe
default, so a malformed LLM JSON degrades to "block" rather than crashing.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .audit import EventAction, emit_event
from .models import GuardrailDecision, Outcome, Rule

# ---------------------------------------------------------------------------
# Consultation request
# ---------------------------------------------------------------------------


RequesterRole = Literal[
    "school_official",
    "outsourced_vendor",
    "parent",
    "eligible_student",
    "researcher",
    "emergency_responder",
    "law_enforcement",
    "third_party",
    "unknown",
]

Purpose = Literal[
    "advising",
    "research",
    "financial_aid",
    "audit_log_inspection",
    "emergency_response",
    "redisclosure",
    "subpoena_compliance",
    "directory_lookup",
    "unknown",
]


class ConsultationRequest(BaseModel):
    """The structured contract the advisor LLM emits before answering."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    query: str
    requester_role: RequesterRole = "unknown"
    purpose: Purpose = "unknown"
    data_requested: list[str] = Field(default_factory=list)
    consent_on_file: bool = False
    student_opted_out_of_directory: bool = False
    emergency_justified: bool = False
    safe_harbor_conditions_met: list[str] = Field(default_factory=list)
    receiver_redisclosing: bool = False
    aggregate_or_de_identified: bool = False


# ---------------------------------------------------------------------------
# Tag derivation
# ---------------------------------------------------------------------------


_DIRECTORY_ITEMS = {
    "name",
    "address",
    "phone",
    "email",
    "institutional_email",
    "major",
    "dates_of_attendance",
    "enrollment_status",
    "degree",
    "honors",
    "weight",  # athletic rosters
    "height",
    "sport",
    "team",
    "roster",
}
_NON_DIRECTORY_ITEMS = {
    "gpa",
    "transcript",
    "test_scores",
    "grades",
    "ssn",
    "social_security_number",
    "disciplinary",
    "financial_aid_amount",
    "health_records",
    "iep",
}


def derive_tags(req: ConsultationRequest) -> set[str]:
    """Deterministically compute the rule-trigger tags for a consultation.

    Keep this pure-functional — every test for the guardrail asserts on the
    output of this + match_rules, never on LLM stochasticity.
    """
    tags: set[str] = {"pii_request", "default_consent_gate", "disclosure"}

    role = req.requester_role
    if role == "school_official":
        tags |= {"school_official_request", "internal_disclosure"}
    elif role == "outsourced_vendor":
        tags |= {"vendor_request", "ai_vendor", "outsourced_vendor", "school_official_request"}
    elif role == "parent":
        tags |= {"parent_request"}
    elif role == "researcher":
        tags |= {"studies_request", "research_request", "third_party_research"}
    elif role == "emergency_responder":
        tags |= {"emergency_request", "health_safety", "time_sensitive"}
    elif role == "law_enforcement":
        tags |= {"subpoena_request", "law_enforcement"}
    elif role == "third_party":
        tags |= {"third_party_forward"}

    purpose = req.purpose
    if purpose == "emergency_response":
        tags |= {"emergency_request", "health_safety", "time_sensitive"}
    elif purpose == "research":
        tags |= {"studies_request", "research_request"}
    elif purpose == "financial_aid":
        tags |= {"financial_aid_request", "title_iv_overlap"}
    elif purpose == "audit_log_inspection":
        tags |= {"audit_log_request", "audit_log_obligation"}
    elif purpose == "redisclosure":
        tags |= {"redisclosure_request", "third_party_forward"}
    elif purpose == "subpoena_compliance":
        tags |= {"subpoena_request", "court_order_request"}
    elif purpose == "directory_lookup":
        tags |= {"directory_info_request"}

    if req.receiver_redisclosing:
        tags |= {"redisclosure_request", "third_party_forward"}

    if req.aggregate_or_de_identified:
        tags |= {"aggregate_request", "statistics_request", "de_identified"}

    if req.data_requested:
        items_lower = {item.lower().replace(" ", "_") for item in req.data_requested}
        if items_lower & _NON_DIRECTORY_ITEMS:
            tags |= {"non_directory_request"}
            if "ssn" in items_lower or "social_security_number" in items_lower:
                tags |= {"ssn_combined"}
        if items_lower & _DIRECTORY_ITEMS and not (items_lower & _NON_DIRECTORY_ITEMS):
            tags |= {"directory_info_request"}
        if items_lower & {"roster", "team", "sport"}:
            tags |= {"directory_info_request"}

    return tags


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------


def match_rules(req: ConsultationRequest, rules: list[Rule]) -> list[Rule]:
    """Return every rule whose trigger set intersects the consultation tags."""
    tags = derive_tags(req)
    return [r for r in rules if set(r.triggers) & tags]


def _has(rules: list[Rule], rule_id: str) -> bool:
    return any(r.id == rule_id for r in rules)


def _any_matching(rules: list[Rule], substring: str) -> bool:
    return any(substring in r.id for r in rules)


# ---------------------------------------------------------------------------
# decide() — the priority cascade
# ---------------------------------------------------------------------------


def decide(
    req: ConsultationRequest,
    rules: list[Rule],
    *,
    model: str = "",
    audit_sink: Path | None = None,
) -> GuardrailDecision:
    """Walk the cascade, return a typed GuardrailDecision."""
    started = time.monotonic()
    matched = match_rules(req, rules)
    matched_ids = [r.id for r in matched]
    citations: list[str] = []

    outcome: Outcome
    response_lines: list[str]

    # ---- 1. Emergency -----------------------------------------------------
    if "emergency_request" in derive_tags(req) and req.emergency_justified:
        outcome = "allow"
        citations = ["34-CFR-99.36", "34-CFR-99.32"]
        response_lines = [
            "Allowed under 34 CFR § 99.36(a) (health/safety emergency).",
            "Required recordkeeping: under § 99.32(a)(5) you must record (i) the articulable "
            "and significant threat that formed the basis for this disclosure and (ii) the "
            "parties to whom the information was disclosed.",
        ]
    # ---- 2. Redisclosure default-block -----------------------------------
    elif "redisclosure_request" in derive_tags(req) and not req.consent_on_file:
        outcome = "block"
        citations = ["34-CFR-99.33"]
        response_lines = [
            "Blocked under 34 CFR § 99.33(a)(1).",
            "A party that receives PII from an education record cannot redisclose it to any "
            "other party without prior consent of the parent or eligible student. Obtain "
            "written consent or use one of the § 99.33(c) carve-outs.",
        ]
    # ---- 3. Parent audit-log request --------------------------------------
    elif "audit_log_request" in derive_tags(req) and req.requester_role in (
        "parent",
        "eligible_student",
    ):
        outcome = "allow"
        citations = ["34-CFR-99.32"]
        response_lines = [
            "Allowed under 34 CFR § 99.32(c)(1).",
            "Parents and eligible students may inspect the record of disclosures the agency "
            "is required to maintain under § 99.32(a)(1).",
        ]
    # ---- 4. SSN combined with directory ----------------------------------
    elif "ssn_combined" in derive_tags(req):
        outcome = "block"
        citations = ["34-CFR-99.37(e)", "34-CFR-99.30"]
        response_lines = [
            "Blocked under 34 CFR § 99.37(e).",
            "Directory information may not be disclosed or confirmed if a student's SSN or "
            "other non-directory data is used (alone or combined) to identify the student. "
            "Get § 99.30 written consent or strip the non-directory element.",
        ]
    # ---- 5. Directory information path -----------------------------------
    elif "directory_info_request" in derive_tags(req):
        citations = ["34-CFR-99.37"]
        if req.student_opted_out_of_directory:
            outcome = "block"
            response_lines = [
                "Blocked under 34 CFR § 99.37(a)(2) + (b).",
                "The student (or their parent) has opted out of directory-information "
                "designation. Opt-outs persist past enrollment unless rescinded; honor the "
                "request and obtain § 99.30 consent if disclosure is required.",
            ]
        else:
            outcome = "escalate_directory_check"
            response_lines = [
                "Escalation: per-student opt-out status required (34 CFR § 99.37).",
                "Confirm with the registrar that the student has NOT opted out of "
                "directory-information designation before disclosing. If opted-out, refuse "
                "and route through § 99.30 consent.",
            ]
    # ---- 6. Studies / de-identified --------------------------------------
    elif "studies_request" in derive_tags(req) or "research_request" in derive_tags(req):
        if req.aggregate_or_de_identified:
            outcome = "allow"
            citations = ["34-CFR-99.31(b)(1)", "34-CFR-99.31(a)(6)"]
            response_lines = [
                "Allowed under 34 CFR § 99.31(b)(1) (de-identified records).",
                "Confirm: removal of all PII has been done with a reasonable de-identification "
                "determination accounting for other reasonably-available information.",
            ]
        else:
            cumulative = {
                "written_agreement_specifying_purpose_scope_duration",
                "use_limited_to_study_purpose",
                "no_personal_identification_outside_org",
                "destroy_when_no_longer_needed",
            }
            met = set(req.safe_harbor_conditions_met)
            if cumulative.issubset(met):
                outcome = "allow"
                citations = ["34-CFR-99.31(a)(6)"]
                response_lines = [
                    "Allowed under 34 CFR § 99.31(a)(6) (studies exception).",
                    "All four cumulative contractual conditions are on file (written agreement "
                    "with purpose/scope/duration, use limitation, no personal identification, "
                    "destroy when no longer needed).",
                ]
            else:
                outcome = "escalate_consent"
                citations = ["34-CFR-99.31(a)(6)"]
                missing = sorted(cumulative - met)
                response_lines = [
                    "Escalation: studies exception requires written agreement.",
                    "Missing contractual conditions under § 99.31(a)(6)(iii)(C): "
                    + ", ".join(missing),
                    "Either complete the written agreement or obtain § 99.30 consent.",
                ]
    # ---- 7. Vendor as school official ------------------------------------
    elif "vendor_request" in derive_tags(req) or "outsourced_vendor" in derive_tags(req):
        cumulative = {
            "performs_institutional_function",
            "under_direct_institutional_control",
            "bound_by_section_99_33_a_redisclosure_limits",
        }
        met = set(req.safe_harbor_conditions_met)
        if cumulative.issubset(met):
            outcome = "allow"
            citations = ["34-CFR-99.31(a)(1)(i)(B)"]
            response_lines = [
                "Allowed under 34 CFR § 99.31(a)(1)(i)(B) (outsourced school official).",
                "All three cumulative safe-harbor conditions verified.",
            ]
        else:
            outcome = "escalate_consent"
            citations = ["34-CFR-99.31(a)(1)(i)(B)"]
            missing = sorted(cumulative - met)
            response_lines = [
                "Escalation: outsourced vendor cannot be treated as a school official.",
                "Required § 99.31(a)(1)(i)(B) conditions not on file: " + ", ".join(missing),
                "Either complete vendor contract amendments or obtain § 99.30 consent before "
                "any further disclosure.",
            ]
    # ---- 8. Financial aid (Title IV) -------------------------------------
    elif "financial_aid_request" in derive_tags(req):
        outcome = "allow"
        citations = ["34-CFR-99.31(a)(4)"]
        response_lines = [
            "Allowed under 34 CFR § 99.31(a)(4).",
            "Disclosure is in connection with financial aid for which the student has applied "
            "or received aid (eligibility / amount / conditions / enforcement).",
        ]
    # ---- 9. Consent on file ----------------------------------------------
    elif req.consent_on_file:
        outcome = "allow"
        citations = ["34-CFR-99.30"]
        response_lines = [
            "Allowed under 34 CFR § 99.30 (consent on file).",
            "Confirm the consent record specifies the records, purpose, and recipient.",
        ]
    # ---- 10. Default block -----------------------------------------------
    else:
        outcome = "block"
        citations = ["34-CFR-99.30"]
        response_lines = [
            "Blocked under 34 CFR § 99.30(a) (default consent rule).",
            "No § 99.31 exception applies and no consent is on file. Obtain signed, dated "
            "written consent that specifies records, purpose, and recipient.",
        ]

    elapsed_ms = int((time.monotonic() - started) * 1000)
    decision = GuardrailDecision(
        id=str(uuid.uuid4()),
        query=req.query,
        timestamp=datetime.now(UTC),
        matched_rules=matched_ids,
        outcome=outcome,
        llm_response="\n".join(response_lines),
        citations_emitted=citations,
        latency_ms=elapsed_ms,
        model=model,
    )

    if audit_sink is not None:
        action_for = {
            "allow": EventAction.GUARDRAIL_ALLOWED,
            "block": EventAction.GUARDRAIL_BLOCKED,
            "escalate_consent": EventAction.GUARDRAIL_ESCALATED_CONSENT,
            "escalate_directory_check": EventAction.GUARDRAIL_ESCALATED_DIRECTORY_CHECK,
        }[outcome]
        emit_event(
            EventAction.GUARDRAIL_CONSULTED,
            payload={
                "decision_id": decision.id,
                "outcome": outcome,
                "matched_rule_count": len(matched_ids),
                "tags": sorted(derive_tags(req)),
            },
            sink=audit_sink,
        )
        emit_event(
            action_for,
            payload={
                "decision_id": decision.id,
                "citations": citations,
                "latency_ms": elapsed_ms,
            },
            sink=audit_sink,
        )

    return decision
