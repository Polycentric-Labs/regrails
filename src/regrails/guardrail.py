"""Guardrail decision engine (v0.2 — FERPA + Title IV, risk-tiered).

A consultation request (constructed by the advisor LLM before answering the
end-user) is fed to :func:`decide`, which:

1. Routes by ``topic``: ``aid_status`` -> Title IV cascade; ``other`` ->
   ``out_of_scope``; ``disclosure`` / ``unknown`` -> the FERPA cascade.
2. Walks the relevant deterministic cascade and produces an :class:`Outcome`
   with citations.
3. Post-processes a **risk tier** + **human_gate_required** flag, formalizing the
   boundary between what an AI may automate (reversible / low-stakes) and what must
   route to a human (irreversible / high-stakes — loss of aid eligibility, default).

The decision is 100% deterministic and made BEFORE any LLM call. The LLM only
renders the user-facing reply (see :mod:`regrails.llm`).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .audit import EventAction, emit_event
from .models import GuardrailDecision, Outcome, RiskTier, Rule

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

# Which regulatory domain the query sits in.
#   disclosure / unknown -> FERPA (education-record disclosure)
#   aid_status           -> Title IV (financial-aid eligibility / SAP advice)
#   other                -> not a regulated student-data matter -> out_of_scope
Topic = Literal["disclosure", "aid_status", "other", "unknown"]

SapStatus = Literal["meeting", "failed_eval", "on_warning", "on_probation", "unknown"]


class ConsultationRequest(BaseModel):
    """The structured contract the advisor LLM emits before answering."""

    model_config = ConfigDict(extra="ignore", use_enum_values=True)

    query: str
    topic: Topic = "unknown"
    requester_role: RequesterRole = "unknown"
    purpose: Purpose = "unknown"
    data_requested: list[str] = Field(default_factory=list)
    # FERPA-path facts
    consent_on_file: bool = False
    student_opted_out_of_directory: bool = False
    emergency_justified: bool = False
    safe_harbor_conditions_met: list[str] = Field(default_factory=list)
    receiver_redisclosing: bool = False
    aggregate_or_de_identified: bool = False
    # Title IV-path facts
    aid_determination_requested: bool = False
    sap_status: SapStatus = "unknown"
    student_in_default: bool | None = None
    appeal_basis_present: bool = False


def normalize_consultation(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw consultation payload before constructing a ``ConsultationRequest``.

    Single source of truth shared by both Vercel endpoints (``web/api/decide.py``
    and ``web/api/reply.py``) so they can never drift. The normalization, in order:

    1. Drop keys whose value is ``None`` or the empty string ``""`` (so absent /
       blank form fields fall through to the model's field defaults rather than
       failing validation).
    2. Default ``query`` to ``""`` if it was dropped or never supplied.
    3. If ``data_requested`` arrived as a CSV **string** (an HTML form sends one
       text field, not a JSON array), split it on commas and strip/​drop blanks.

    The input dict is never mutated; a new dict is returned. ``False`` and ``0``
    are preserved (they are neither ``None`` nor ``""``) — important for the
    boolean FERPA/Title IV facts.
    """
    cons = {k: v for k, v in (data or {}).items() if v is not None and v != ""}
    cons.setdefault("query", "")
    if isinstance(cons.get("data_requested"), str):
        cons["data_requested"] = [s.strip() for s in cons["data_requested"].split(",") if s.strip()]
    return cons


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

    Pure-functional: every guardrail test asserts on the output of this + the
    cascade, never on LLM stochasticity. FERPA and Title IV occupy disjoint tag
    spaces so :func:`match_rules` never cross-matches frameworks.
    """
    if req.topic == "other":
        return set()

    if req.topic == "aid_status":
        tags: set[str] = {"aid_status_query", "sap_question", "eligibility_question", "aid_eligibility"}
        if req.aid_determination_requested:
            tags |= {"aid_determination"}
        if req.sap_status == "failed_eval":
            tags |= {"sap_evaluation", "sap_termination"}
        elif req.sap_status == "on_warning":
            tags |= {"sap_warning", "aid_status"}
        elif req.sap_status == "on_probation":
            tags |= {"sap_probation", "aid_status"}
        if req.student_in_default is True:
            tags |= {"loan_default"}
        if req.appeal_basis_present:
            tags |= {"sap_appeal"}
        if req.purpose == "financial_aid":
            tags |= {"sap_policy"}
        return tags

    # FERPA / disclosure / unknown -------------------------------------------
    tags = {"pii_request", "default_consent_gate", "disclosure"}

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


def match_rules(req: ConsultationRequest, rules: list[Rule]) -> list[Rule]:
    """Return every rule whose trigger set intersects the consultation tags."""
    tags = derive_tags(req)
    return [r for r in rules if set(r.triggers) & tags]


# ---------------------------------------------------------------------------
# FERPA cascade (behavior preserved verbatim from v0.1)
# ---------------------------------------------------------------------------


def _decide_ferpa(req: ConsultationRequest) -> tuple[Outcome, list[str], list[str]]:
    tags = derive_tags(req)

    # ---- 1. Emergency -----------------------------------------------------
    if "emergency_request" in tags and req.emergency_justified:
        return (
            "allow",
            ["34-CFR-99.36", "34-CFR-99.32"],
            [
                "Allowed under 34 CFR § 99.36(a) (health/safety emergency).",
                "Required recordkeeping: under § 99.32(a)(5) you must record (i) the articulable "
                "and significant threat that formed the basis for this disclosure and (ii) the "
                "parties to whom the information was disclosed.",
            ],
        )
    # ---- 2. Redisclosure default-block -----------------------------------
    if "redisclosure_request" in tags and not req.consent_on_file:
        return (
            "block",
            ["34-CFR-99.33"],
            [
                "Blocked under 34 CFR § 99.33(a)(1).",
                "A party that receives PII from an education record cannot redisclose it to any "
                "other party without prior consent of the parent or eligible student. Obtain "
                "written consent or use one of the § 99.33(c) carve-outs.",
            ],
        )
    # ---- 3. Parent audit-log request --------------------------------------
    if "audit_log_request" in tags and req.requester_role in ("parent", "eligible_student"):
        return (
            "allow",
            ["34-CFR-99.32"],
            [
                "Allowed under 34 CFR § 99.32(c)(1).",
                "Parents and eligible students may inspect the record of disclosures the agency "
                "is required to maintain under § 99.32(a)(1).",
            ],
        )
    # ---- 4. SSN combined with directory ----------------------------------
    if "ssn_combined" in tags:
        return (
            "block",
            ["34-CFR-99.37(e)", "34-CFR-99.30"],
            [
                "Blocked under 34 CFR § 99.37(e).",
                "Directory information may not be disclosed or confirmed if a student's SSN or "
                "other non-directory data is used (alone or combined) to identify the student. "
                "Get § 99.30 written consent or strip the non-directory element.",
            ],
        )
    # ---- 5. Directory information path -----------------------------------
    if "directory_info_request" in tags:
        if req.student_opted_out_of_directory:
            return (
                "block",
                ["34-CFR-99.37"],
                [
                    "Blocked under 34 CFR § 99.37(a)(2) + (b).",
                    "The student (or their parent) has opted out of directory-information "
                    "designation. Opt-outs persist past enrollment unless rescinded; honor the "
                    "request and obtain § 99.30 consent if disclosure is required.",
                ],
            )
        return (
            "escalate_directory_check",
            ["34-CFR-99.37"],
            [
                "Escalation: per-student opt-out status required (34 CFR § 99.37).",
                "Confirm with the registrar that the student has NOT opted out of "
                "directory-information designation before disclosing. If opted-out, refuse "
                "and route through § 99.30 consent.",
            ],
        )
    # ---- 6. Studies / de-identified --------------------------------------
    if "studies_request" in tags or "research_request" in tags:
        if req.aggregate_or_de_identified:
            return (
                "allow",
                ["34-CFR-99.31(b)(1)", "34-CFR-99.31(a)(6)"],
                [
                    "Allowed under 34 CFR § 99.31(b)(1) (de-identified records).",
                    "Confirm: removal of all PII has been done with a reasonable de-identification "
                    "determination accounting for other reasonably-available information.",
                ],
            )
        cumulative = {
            "written_agreement_specifying_purpose_scope_duration",
            "use_limited_to_study_purpose",
            "no_personal_identification_outside_org",
            "destroy_when_no_longer_needed",
        }
        met = set(req.safe_harbor_conditions_met)
        if cumulative.issubset(met):
            return (
                "allow",
                ["34-CFR-99.31(a)(6)"],
                [
                    "Allowed under 34 CFR § 99.31(a)(6) (studies exception).",
                    "All four cumulative contractual conditions are on file (written agreement "
                    "with purpose/scope/duration, use limitation, no personal identification, "
                    "destroy when no longer needed).",
                ],
            )
        missing = sorted(cumulative - met)
        return (
            "escalate_consent",
            ["34-CFR-99.31(a)(6)"],
            [
                "Escalation: studies exception requires written agreement.",
                "Missing contractual conditions under § 99.31(a)(6)(iii)(C): " + ", ".join(missing),
                "Either complete the written agreement or obtain § 99.30 consent.",
            ],
        )
    # ---- 7. Vendor as school official ------------------------------------
    if "vendor_request" in tags or "outsourced_vendor" in tags:
        cumulative = {
            "performs_institutional_function",
            "under_direct_institutional_control",
            "bound_by_section_99_33_a_redisclosure_limits",
        }
        met = set(req.safe_harbor_conditions_met)
        if cumulative.issubset(met):
            return (
                "allow",
                ["34-CFR-99.31(a)(1)(i)(B)"],
                [
                    "Allowed under 34 CFR § 99.31(a)(1)(i)(B) (outsourced school official).",
                    "All three cumulative safe-harbor conditions verified.",
                ],
            )
        missing = sorted(cumulative - met)
        return (
            "escalate_consent",
            ["34-CFR-99.31(a)(1)(i)(B)"],
            [
                "Escalation: outsourced vendor cannot be treated as a school official.",
                "Required § 99.31(a)(1)(i)(B) conditions not on file: " + ", ".join(missing),
                "Either complete vendor contract amendments or obtain § 99.30 consent before "
                "any further disclosure.",
            ],
        )
    # ---- 8. Financial aid (FERPA disclosure to aid processor) ------------
    if "financial_aid_request" in tags:
        return (
            "allow",
            ["34-CFR-99.31(a)(4)"],
            [
                "Allowed under 34 CFR § 99.31(a)(4).",
                "Disclosure is in connection with financial aid for which the student has applied "
                "or received aid (eligibility / amount / conditions / enforcement).",
            ],
        )
    # ---- 9. Consent on file ----------------------------------------------
    if req.consent_on_file:
        return (
            "allow",
            ["34-CFR-99.30"],
            [
                "Allowed under 34 CFR § 99.30 (consent on file).",
                "Confirm the consent record specifies the records, purpose, and recipient.",
            ],
        )
    # ---- 10. Default block -----------------------------------------------
    return (
        "block",
        ["34-CFR-99.30"],
        [
            "Blocked under 34 CFR § 99.30(a) (default consent rule).",
            "No § 99.31 exception applies and no consent is on file. Obtain signed, dated "
            "written consent that specifies records, purpose, and recipient.",
        ],
    )


# ---------------------------------------------------------------------------
# Title IV cascade (v0.2)
# ---------------------------------------------------------------------------


def _decide_title_iv(req: ConsultationRequest) -> tuple[Outcome, list[str], list[str]]:
    # ---- 1. Loan default — high-stakes eligibility bar -------------------
    if req.student_in_default is True:
        return (
            "escalate_human_review",
            ["34-CFR-668.32(g)(1)"],
            [
                "A student in default on a Title IV loan is not eligible for further Title IV "
                "aid under 34 CFR § 668.32(g)(1), absent a § 668.35 exception.",
                "Do not confirm eligibility. Route the student to the financial-aid office to "
                "resolve the default (e.g. rehabilitation or consolidation) before any aid "
                "determination is made.",
            ],
        )
    # ---- 2. Failed SAP evaluation + determination asked — human gate -----
    if req.sap_status == "failed_eval" and req.aid_determination_requested:
        return (
            "escalate_human_review",
            ["34-CFR-668.34(a)(7)"],
            [
                "A student who has not met the required GPA or pace is no longer eligible for "
                "Title IV aid under 34 CFR § 668.34(a)(7), subject to the warning/probation paths.",
                "This is a high-stakes determination reserved to the institution. Do not confirm "
                "continued aid; route to the financial-aid office, which may apply financial aid "
                "warning or probation.",
            ],
        )
    # ---- 3. Determination asked but SAP status unknown — insufficient ----
    if (
        req.aid_determination_requested
        and req.sap_status == "unknown"
        and req.student_in_default is None
    ):
        return (
            "insufficient_facts",
            ["34-CFR-668.34(a)(3)"],
            [
                "Cannot assess: a Title IV aid determination depends on the student's "
                "satisfactory-academic-progress evaluation (34 CFR § 668.34(a)(3)) and "
                "eligibility facts that are not present in this request.",
                "Provide the SAP evaluation result and loan-default status, or route to the "
                "financial-aid office.",
            ],
        )
    # ---- 4. Financial aid warning — informational allow ------------------
    if req.sap_status == "on_warning":
        return (
            "allow",
            ["34-CFR-668.34(a)(8)(i)"],
            [
                "You may explain that a student on financial aid warning may continue to receive "
                "Title IV aid for one payment period despite a SAP determination "
                "(34 CFR § 668.34(a)(8)(i)); no appeal is required for the warning itself.",
                "Do not extend the warning or promise aid beyond that payment period; the "
                "institution assigns and ends the status.",
            ],
        )
    # ---- 5. Financial aid probation — informational allow ----------------
    if req.sap_status == "on_probation":
        cites = ["34-CFR-668.34(a)(8)(ii)"]
        lines = [
            "You may explain that a student on financial aid probation may receive Title IV funds "
            "for one payment period and may be required to follow specific terms or an academic "
            "plan (34 CFR § 668.34(a)(8)(ii)).",
        ]
        if req.appeal_basis_present:
            cites.append("34-CFR-668.34(a)(9)(ii)")
            lines.append(
                "A SAP appeal may rest on the death of a relative, the student's injury or "
                "illness, or other special circumstances (34 CFR § 668.34(a)(9)(ii))."
            )
        lines.append(
            "The probation status and any academic plan are set by the institution, not the advisor."
        )
        return ("allow", cites, lines)
    # ---- 6. Eligibility determination requested — human gate -------------
    if req.aid_determination_requested:
        return (
            "escalate_human_review",
            ["34-CFR-668.32"],
            [
                "A Title IV eligibility determination (34 CFR § 668.32) rests on multiple "
                "institutional and ED facts (enrollment, SAP, default, loan limits, SSN, etc.).",
                "Do not issue a yes/no eligibility answer; route to the financial-aid office. "
                "You may explain the criteria in general terms.",
            ],
        )
    # ---- 7. General informational question — allow -----------------------
    return (
        "allow",
        ["34-CFR-668.34", "34-CFR-668.32"],
        [
            "You may explain the Title IV satisfactory-academic-progress and eligibility rules in "
            "general terms.",
            "Any determination about a specific student's eligibility or status is made by the "
            "institution's financial-aid office, not the AI advisor.",
        ],
    )


# ---------------------------------------------------------------------------
# Risk tier + human gate
# ---------------------------------------------------------------------------


def _risk_for(outcome: Outcome, framework: str, citations: list[str]) -> tuple[RiskTier, bool]:
    """Map an outcome to (risk_tier, human_gate_required).

    The governance thesis: reversible/low-stakes actions are safe to automate;
    irreversible/high-stakes actions (loss of aid eligibility, default) keep a
    mandatory human gate.
    """
    if outcome == "escalate_human_review":
        return ("high", True)
    if outcome == "block":
        return ("medium", False)
    if outcome in ("escalate_consent", "escalate_directory_check"):
        return ("medium", False)
    if outcome in ("insufficient_facts", "out_of_scope"):
        return ("low", False)
    # allow
    if framework == "Title IV":
        return ("medium", False)
    if any("99.36" in c for c in citations):
        return ("medium", False)
    return ("low", False)


_ACTION_FOR: dict[Outcome, EventAction] = {
    "allow": EventAction.GUARDRAIL_ALLOWED,
    "block": EventAction.GUARDRAIL_BLOCKED,
    "escalate_consent": EventAction.GUARDRAIL_ESCALATED_CONSENT,
    "escalate_directory_check": EventAction.GUARDRAIL_ESCALATED_DIRECTORY_CHECK,
    "escalate_human_review": EventAction.GUARDRAIL_ESCALATED_HUMAN_REVIEW,
    "insufficient_facts": EventAction.GUARDRAIL_INSUFFICIENT_FACTS,
    "out_of_scope": EventAction.GUARDRAIL_OUT_OF_SCOPE,
}


# ---------------------------------------------------------------------------
# decide() — orchestrator
# ---------------------------------------------------------------------------


def decide(
    req: ConsultationRequest,
    rules: list[Rule],
    *,
    model: str = "",
    audit_sink: Path | None = None,
) -> GuardrailDecision:
    """Route + walk the relevant cascade + assign risk tier; return a decision."""
    started = time.monotonic()

    if req.topic == "other":
        framework = "n/a"
        outcome: Outcome = "out_of_scope"
        citations: list[str] = []
        response_lines = [
            "Out of scope: this query is not a regulated student-records or financial-aid "
            "matter, so no RegRails rule applies.",
            "An advisor may answer it normally without a compliance gate.",
        ]
        matched_ids: list[str] = []
    elif req.topic == "aid_status":
        framework = "Title IV"
        outcome, citations, response_lines = _decide_title_iv(req)
        matched_ids = [r.id for r in match_rules(req, rules)]
    else:
        framework = "FERPA"
        outcome, citations, response_lines = _decide_ferpa(req)
        matched_ids = [r.id for r in match_rules(req, rules)]

    risk_tier, human_gate = _risk_for(outcome, framework, citations)

    elapsed_ms = int((time.monotonic() - started) * 1000)
    decision = GuardrailDecision(
        id=str(uuid.uuid4()),
        query=req.query,
        framework=framework,
        timestamp=datetime.now(UTC),
        matched_rules=matched_ids,
        outcome=outcome,
        risk_tier=risk_tier,
        human_gate_required=human_gate,
        llm_response="\n".join(response_lines),
        citations_emitted=citations,
        latency_ms=elapsed_ms,
        model=model,
    )

    if audit_sink is not None:
        emit_event(
            EventAction.GUARDRAIL_CONSULTED,
            payload={
                "decision_id": decision.id,
                "framework": framework,
                "outcome": outcome,
                "risk_tier": risk_tier,
                "human_gate_required": human_gate,
                "matched_rule_count": len(matched_ids),
                "tags": sorted(derive_tags(req)),
            },
            sink=audit_sink,
        )
        emit_event(
            _ACTION_FOR[outcome],
            payload={
                "decision_id": decision.id,
                "citations": citations,
                "risk_tier": risk_tier,
                "human_gate_required": human_gate,
                "latency_ms": elapsed_ms,
            },
            sink=audit_sink,
        )

    return decision
