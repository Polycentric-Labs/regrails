"""Tests for regrails.audit."""

from __future__ import annotations

import json
from pathlib import Path

from regrails.audit import EventAction, emit_event


class TestEventAction:
    def test_values_are_strings_and_namespaced(self) -> None:
        for action in EventAction:
            assert isinstance(action.value, str)
            assert action.value.startswith("regrails.")

    def test_values_unique(self) -> None:
        values = [a.value for a in EventAction]
        assert len(values) == len(set(values))


class TestEmitEvent:
    def test_returns_dict_with_required_fields(self) -> None:
        event = emit_event(EventAction.RULE_ENCODED, payload={"rule_id": "FERPA-99.30-1"})
        assert event["action"] == "regrails.encode.rule_encoded"
        assert event["payload"] == {"rule_id": "FERPA-99.30-1"}
        assert "ts" in event
        assert event["ts"].endswith("+00:00")  # tz-aware ISO 8601

    def test_payload_defaults_to_empty_dict(self) -> None:
        event = emit_event(EventAction.GUARDRAIL_CONSULTED)
        assert event["payload"] == {}

    def test_appends_to_sink_as_jsonl(self, tmp_path: Path) -> None:
        sink = tmp_path / "audit.jsonl"
        emit_event(EventAction.RULE_ENCODED, payload={"n": 1}, sink=sink)
        emit_event(EventAction.GUARDRAIL_BLOCKED, payload={"n": 2}, sink=sink)
        lines = sink.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["action"] == "regrails.encode.rule_encoded"
        assert second["action"] == "regrails.guardrail.blocked"
        assert second["payload"]["n"] == 2

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        sink = tmp_path / "subdir" / "deeper" / "audit.jsonl"
        emit_event(EventAction.LLM_CALL_SUCCEEDED, sink=sink)
        assert sink.exists()
