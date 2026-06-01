"""Export guardrail decisions as SARIF 2.1.0.

SARIF (Static Analysis Results Interchange Format) is what GitHub code-scanning
renders natively. Emitting decisions as SARIF means a CI run can FAIL a pull
request when an AI workflow would have made a prohibited disclosure or a
high-stakes aid determination: ``block`` / ``escalate_human_review`` become SARIF
``error`` results, with the controlling CFR citation as the ``ruleId``.

HONESTY: this is structurally-valid SARIF 2.1.0 (shape asserted in tests); the
claim is "emits SARIF 2.1.0," not "SARIF-certified."
"""

from __future__ import annotations

from typing import Any

from .models import GuardrailDecision

# Outcome -> SARIF level. block / human-review are hard failures; the softer
# escalations are warnings; informational outcomes are note/none.
_LEVEL: dict[str, str] = {
    "block": "error",
    "escalate_human_review": "error",
    "escalate_consent": "warning",
    "escalate_directory_check": "warning",
    "insufficient_facts": "note",
    "out_of_scope": "none",
    "allow": "none",
}

INFORMATION_URI = "https://github.com/Polycentric-Labs/regrails"


def decision_to_result(decision: GuardrailDecision) -> dict[str, Any]:
    rule_id = decision.citations_emitted[0] if decision.citations_emitted else decision.framework
    return {
        "ruleId": rule_id,
        "level": _LEVEL.get(decision.outcome, "none"),
        "message": {"text": decision.llm_response or decision.outcome},
        "properties": {
            "outcome": decision.outcome,
            "risk_tier": decision.risk_tier,
            "human_gate_required": decision.human_gate_required,
            "framework": decision.framework,
            "citations": decision.citations_emitted,
        },
    }


def to_sarif(decisions: list[GuardrailDecision]) -> dict[str, Any]:
    """Build a SARIF 2.1.0 log from one or more GuardrailDecisions."""
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "RegRails",
                        "informationUri": INFORMATION_URI,
                        "version": _driver_version(),
                        "rules": [],
                    }
                },
                "results": [decision_to_result(d) for d in decisions],
            }
        ],
    }


def _driver_version() -> str:
    from . import __version__

    return __version__
