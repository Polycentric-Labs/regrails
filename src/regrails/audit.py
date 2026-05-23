"""Audit-event enum and JSONL emitter.

Mirrors Evidentia's ``EventAction(str, Enum)`` pattern from
``packages/evidentia-core/src/evidentia_core/audit/events.py`` — string-valued
enum so JSON serialization is stable and grep-friendly.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class EventAction(StrEnum):
    """Auditable actions emitted by RegRails."""

    # Encoding
    RULE_ENCODED = "regrails.encode.rule_encoded"
    SECTION_LOADED = "regrails.encode.section_loaded"

    # Faithfulness
    FAITHFULNESS_CHECK_PASSED = "regrails.faithfulness.check_passed"
    FAITHFULNESS_CHECK_FAILED = "regrails.faithfulness.check_failed"

    # Research
    RESEARCH_STREAM_FETCHED = "regrails.research.stream_fetched"
    RESEARCH_STREAM_FAILED = "regrails.research.stream_failed"

    # Guardrail
    GUARDRAIL_CONSULTED = "regrails.guardrail.consulted"
    GUARDRAIL_ALLOWED = "regrails.guardrail.allowed"
    GUARDRAIL_BLOCKED = "regrails.guardrail.blocked"
    GUARDRAIL_ESCALATED_CONSENT = "regrails.guardrail.escalated_consent"
    GUARDRAIL_ESCALATED_DIRECTORY_CHECK = "regrails.guardrail.escalated_directory_check"

    # LLM
    LLM_CALL_SUCCEEDED = "regrails.llm.call_succeeded"
    LLM_CALL_FAILED = "regrails.llm.call_failed"
    LLM_FALLBACK_USED = "regrails.llm.fallback_used"


def emit_event(
    action: EventAction,
    *,
    payload: dict[str, Any] | None = None,
    sink: Path | None = None,
) -> dict[str, Any]:
    """Build an audit event dict and (optionally) append it to ``sink`` as JSONL.

    Returns the event dict so callers can also inspect / forward it. Caller is
    responsible for choosing the sink — there is no global default file.

    The schema is intentionally minimal for the POC; production would add
    request-id, principal, source-ip, signatures, etc.
    """
    event: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "action": action.value,
        "payload": payload or {},
    }
    if sink is not None:
        sink.parent.mkdir(parents=True, exist_ok=True)
        with sink.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(event, separators=(",", ":")) + "\n")
    return event
