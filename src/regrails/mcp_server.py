"""RegRails MCP server — expose the deterministic guardrail as agent-callable tools.

An AI agent (Claude Desktop/Code, or any MCP client) calls these tools BEFORE
answering a question about a student's education records or financial aid. The
decision is made entirely by the deterministic engine (no LLM); the agent uses the
returned ``GuardrailDecision`` to shape — or refuse — its reply. This is the
"tool use, human-in-the-loop" pattern: high-stakes outcomes carry
``human_gate_required=True`` and must be routed to a human.

Borrows the FastMCP shape + the "secrets never travel as tool args" trust model
from Evidentia's ``evidentia-mcp`` server.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .encode import load_all_rules, load_all_sections
from .faithfulness import check_sections
from .guardrail import ConsultationRequest, decide
from .models import Rule

_INSTRUCTIONS = (
    "RegRails encodes FERPA (34 CFR Part 99) and a Title IV subset (34 CFR Part 668) as "
    "machine-readable rules. Call `consult_guardrail` BEFORE answering any question about a "
    "student's education records or financial-aid eligibility. Honor the returned outcome: on "
    "`block` or any `escalate_*` outcome, do NOT answer the underlying question; when "
    "`human_gate_required` is true the decision is reserved to a human (e.g. the financial-aid "
    "office). Decisions are deterministic and made without any LLM."
)

server = FastMCP("regrails", instructions=_INSTRUCTIONS)

_RULES: list[Rule] | None = None


def _rules() -> list[Rule]:
    global _RULES
    if _RULES is None:
        _RULES = load_all_rules()
    return _RULES


def consult_guardrail(
    query: str,
    topic: str = "unknown",
    requester_role: str = "unknown",
    purpose: str = "unknown",
    data_requested: list[str] | None = None,
    aid_determination_requested: bool = False,
    sap_status: str = "unknown",
    student_in_default: bool | None = None,
    consent_on_file: bool = False,
    student_opted_out_of_directory: bool = False,
    emergency_justified: bool = False,
    safe_harbor_conditions_met: list[str] | None = None,
) -> dict[str, Any]:
    """Consult the deterministic FERPA/Title IV guardrail before answering.

    Returns a typed GuardrailDecision as a dict: ``outcome``, ``risk_tier``,
    ``human_gate_required``, ``citations_emitted``, ``matched_rules``, ``framework``.
    No LLM is involved — the engine decides.

    Key inputs: ``topic`` is ``disclosure`` (FERPA records), ``aid_status`` (Title IV
    financial aid), or ``other`` (out of scope). For Title IV, set ``sap_status``
    (``meeting``/``failed_eval``/``on_warning``/``on_probation``), ``student_in_default``,
    and ``aid_determination_requested`` when the user wants a yes/no eligibility answer.
    """
    req = ConsultationRequest.model_validate(
        {
            "query": query,
            "topic": topic,
            "requester_role": requester_role,
            "purpose": purpose,
            "data_requested": data_requested or [],
            "aid_determination_requested": aid_determination_requested,
            "sap_status": sap_status,
            "student_in_default": student_in_default,
            "consent_on_file": consent_on_file,
            "student_opted_out_of_directory": student_opted_out_of_directory,
            "emergency_justified": emergency_justified,
            "safe_harbor_conditions_met": safe_harbor_conditions_met or [],
        }
    )
    return decide(req, _rules()).model_dump(mode="json")


def list_rules(framework: str = "all") -> list[dict[str, Any]]:
    """List the encoded rules (FERPA + Title IV). Filter by ``framework`` or pass ``all``."""
    rules = _rules()
    if framework != "all":
        rules = [r for r in rules if r.framework == framework]
    return [r.model_dump(mode="json") for r in rules]


def check_faithfulness() -> dict[str, Any]:
    """Verify every encoded rule's source_quote is verbatim in the bundled CFR text.

    Returns ``{"passed": int, "total": int}``.
    """
    report = check_sections(load_all_sections())
    return {"passed": report.passed_count, "total": len(report.results)}


server.tool()(consult_guardrail)
server.tool()(list_rules)
server.tool()(check_faithfulness)


def serve() -> None:
    """Run the MCP server over stdio (entry point for ``regrails-mcp`` / ``regrails mcp serve``)."""
    server.run()
