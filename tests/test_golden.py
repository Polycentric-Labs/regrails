"""Golden-corpus regression tests.

Each scenario in ``tests/golden/*.jsonl`` pins the deterministic engine's
(outcome, risk_tier, human_gate, citations) for a concrete fact pattern. This is
the reviewer-grade behavioral contract: change the engine and these must still hold
(or be deliberately updated).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from regrails.encode import load_all_rules
from regrails.guardrail import ConsultationRequest, decide

GOLDEN_DIR = Path(__file__).parent / "golden"


def _load() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in sorted(GOLDEN_DIR.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


SCENARIOS = _load()
RULES = load_all_rules()


def test_corpus_nonempty() -> None:
    assert len(SCENARIOS) >= 20, "golden corpus should be substantial"


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["scenario_id"] for s in SCENARIOS])
def test_golden_scenario(sc: dict[str, Any]) -> None:
    decision = decide(ConsultationRequest(**sc["consultation"]), RULES)
    assert decision.outcome == sc["expected_outcome"], (
        f"{sc['scenario_id']}: outcome {decision.outcome!r} != {sc['expected_outcome']!r}"
    )
    assert decision.risk_tier == sc["expected_risk_tier"], (
        f"{sc['scenario_id']}: risk_tier {decision.risk_tier!r} != {sc['expected_risk_tier']!r}"
    )
    assert decision.human_gate_required == sc["expected_human_gate"], (
        f"{sc['scenario_id']}: human_gate {decision.human_gate_required} != "
        f"{sc['expected_human_gate']}"
    )
    for cite in sc["expected_citations_contains"]:
        assert cite in decision.citations_emitted, (
            f"{sc['scenario_id']}: expected citation {cite!r} not in {decision.citations_emitted}"
        )


def test_unique_scenario_ids() -> None:
    ids = [s["scenario_id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids))
