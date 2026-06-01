"""Audit-event enum, JSONL emitter, and hash-chained decision provenance.

Two layers:

1. **Event log** (``emit_event``) — append-only JSONL of named actions. Mirrors
   Evidentia's ``EventAction(str, Enum)`` pattern.
2. **Decision provenance** (``append_decision`` / ``verify_chain``) — a
   tamper-evident, hash-chained log of ``GuardrailDecision`` records. Each record
   stores ``prev_hash`` and a ``record_hash = SHA-256(prev_hash + canonical(decision))``.
   Editing, reordering, inserting, or deleting any record breaks the chain, which
   ``verify_chain`` detects. This echoes the cryptographic evidence-binding idea in
   Evidentia (Sigstore-signed artifacts) at POC scale: no keys, just a verifiable chain.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .ids import sha256_hex

GENESIS_HASH = "0" * 64


class EventAction(str, Enum):
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
    GUARDRAIL_ESCALATED_HUMAN_REVIEW = "regrails.guardrail.escalated_human_review"
    GUARDRAIL_INSUFFICIENT_FACTS = "regrails.guardrail.insufficient_facts"
    GUARDRAIL_OUT_OF_SCOPE = "regrails.guardrail.out_of_scope"

    # Provenance
    DECISION_RECORDED = "regrails.provenance.decision_recorded"
    AUDIT_CHAIN_VERIFIED = "regrails.provenance.chain_verified"
    AUDIT_CHAIN_BROKEN = "regrails.provenance.chain_broken"

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
    """Build an audit event dict and (optionally) append it to ``sink`` as JSONL."""
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


# ---------------------------------------------------------------------------
# Hash-chained decision provenance
# ---------------------------------------------------------------------------


def _canonical(decision: dict[str, Any]) -> str:
    """Stable canonical JSON for hashing (sorted keys, no insignificant whitespace)."""
    return json.dumps(decision, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _last_record_hash(path: Path) -> str:
    """Return the record_hash of the last record in the chain, or GENESIS if empty."""
    if not path.exists():
        return GENESIS_HASH
    last = GENESIS_HASH
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        last = rec.get("record_hash", last)
    return last


def append_decision(decision_dict: dict[str, Any], sink: Path) -> str:
    """Append a GuardrailDecision (as a dict) to the hash-chained log at ``sink``.

    Returns the new record_hash. The decision dict should already be JSON-mode
    (e.g. ``decision.model_dump(mode="json")``).
    """
    sink.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = _last_record_hash(sink)
    record_hash = sha256_hex(prev_hash + _canonical(decision_dict))
    record = {"prev_hash": prev_hash, "record_hash": record_hash, "decision": decision_dict}
    with sink.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, separators=(",", ":")) + "\n")
    return record_hash


def verify_chain(path: Path) -> tuple[bool, list[str]]:
    """Verify the hash chain at ``path``. Returns ``(ok, problems)``.

    Checks, for every record in order: (a) ``prev_hash`` links to the prior
    record's ``record_hash`` (genesis for the first), and (b) the stored
    ``record_hash`` equals ``SHA-256(prev_hash + canonical(decision))`` — so any
    edit to a stored decision is detected.
    """
    problems: list[str] = []
    if not path.exists():
        return False, [f"chain file not found: {path}"]

    expected_prev = GENESIS_HASH
    count = 0
    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        raw = raw.strip()
        if not raw:
            continue
        count += 1
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError as exc:
            problems.append(f"record {idx}: invalid JSON ({exc})")
            continue
        prev = rec.get("prev_hash")
        stored = rec.get("record_hash")
        decision = rec.get("decision")
        if prev != expected_prev:
            problems.append(
                f"record {idx} ({_rec_id(decision)}): prev_hash linkage broken "
                f"(expected {expected_prev[:12]}..., got {str(prev)[:12]}...)"
            )
        recomputed = sha256_hex(str(prev) + _canonical(decision)) if decision is not None else None
        if recomputed != stored:
            problems.append(
                f"record {idx} ({_rec_id(decision)}): record_hash mismatch — "
                f"decision content was altered after writing"
            )
        expected_prev = stored if isinstance(stored, str) else expected_prev
    if count == 0:
        problems.append("chain is empty")
    return (len(problems) == 0), problems


def _rec_id(decision: dict[str, Any] | None) -> str:
    if not isinstance(decision, dict):
        return "?"
    return str(decision.get("id", "?"))[:8]
