"""Tests for regrails.audit — event log + hash-chained decision provenance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from regrails.audit import (
    GENESIS_HASH,
    EventAction,
    append_decision,
    emit_event,
    verify_chain,
)


class TestEventAction:
    def test_values_are_strings_and_namespaced(self) -> None:
        for action in EventAction:
            assert isinstance(action.value, str)
            assert action.value.startswith("regrails.")

    def test_values_unique(self) -> None:
        values = [a.value for a in EventAction]
        assert len(values) == len(set(values))

    def test_new_v2_actions_present(self) -> None:
        names = {a.name for a in EventAction}
        assert {"GUARDRAIL_ESCALATED_HUMAN_REVIEW", "GUARDRAIL_INSUFFICIENT_FACTS",
                "GUARDRAIL_OUT_OF_SCOPE", "DECISION_RECORDED"}.issubset(names)


class TestEmitEvent:
    def test_returns_dict_with_required_fields(self) -> None:
        event = emit_event(EventAction.RULE_ENCODED, payload={"rule_id": "X"})
        assert event["action"] == "regrails.encode.rule_encoded"
        assert event["payload"] == {"rule_id": "X"}
        assert event["ts"].endswith("+00:00")

    def test_appends_jsonl(self, tmp_path: Path) -> None:
        sink = tmp_path / "audit.jsonl"
        emit_event(EventAction.RULE_ENCODED, payload={"n": 1}, sink=sink)
        emit_event(EventAction.GUARDRAIL_BLOCKED, payload={"n": 2}, sink=sink)
        lines = sink.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2


def _decision(i: int) -> dict[str, Any]:
    return {"id": f"dec-{i}", "outcome": "block", "citations_emitted": ["34-CFR-99.30"]}


class TestHashChain:
    def test_first_record_links_to_genesis(self, tmp_path: Path) -> None:
        sink = tmp_path / "chain.jsonl"
        append_decision(_decision(1), sink)
        rec = json.loads(sink.read_text(encoding="utf-8").splitlines()[0])
        assert rec["prev_hash"] == GENESIS_HASH
        assert len(rec["record_hash"]) == 64

    def test_chain_of_three_verifies(self, tmp_path: Path) -> None:
        sink = tmp_path / "chain.jsonl"
        for i in range(3):
            append_decision(_decision(i), sink)
        ok, problems = verify_chain(sink)
        assert ok, problems
        assert problems == []

    def test_tamper_breaks_chain(self, tmp_path: Path) -> None:
        sink = tmp_path / "chain.jsonl"
        for i in range(3):
            append_decision(_decision(i), sink)
        # Tamper: flip the outcome in the middle record.
        lines = sink.read_text(encoding="utf-8").splitlines()
        rec = json.loads(lines[1])
        rec["decision"]["outcome"] = "allow"  # silently altered
        lines[1] = json.dumps(rec, separators=(",", ":"))
        sink.write_text("\n".join(lines) + "\n", encoding="utf-8")

        ok, problems = verify_chain(sink)
        assert ok is False
        assert any("record_hash mismatch" in p for p in problems)

    def test_deletion_breaks_chain(self, tmp_path: Path) -> None:
        sink = tmp_path / "chain.jsonl"
        for i in range(3):
            append_decision(_decision(i), sink)
        lines = sink.read_text(encoding="utf-8").splitlines()
        del lines[1]  # drop a record
        sink.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, problems = verify_chain(sink)
        assert ok is False
        assert any("linkage broken" in p for p in problems)

    def test_missing_file(self, tmp_path: Path) -> None:
        ok, problems = verify_chain(tmp_path / "nope.jsonl")
        assert ok is False
        assert problems
