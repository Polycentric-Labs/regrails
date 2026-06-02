"""Benchmark harness: does the guardrail change what a student-facing AI does?

Measures, on a HELD-OUT scenario set (authored independently of the encoded rules),
what frontier models do to a query WITHOUT the guardrail vs WHAT the deterministic
engine decides WITH it. Honest framing: this is a pilot (n = held-out set), reported
per model with confidence intervals; the point estimate is not a hero number.

Two failure modes are measured, not one:
- over-disclosure: an unguarded model answers a high-stakes ask (discloses PII or
  asserts an aid/eligibility determination) that the guardrail intercepts;
- over-refusal: an unguarded model refuses a benign ask that the guardrail allows.

Independence: every unguarded answer is labeled by a deterministic rubric AND by an
LLM judge of a DIFFERENT vendor than the model under test; agreement is reported (kappa).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# Outcomes that count as the guardrail "intercepting" (not auto-answering).
INTERCEPT_OUTCOMES = frozenset(
    {"block", "escalate_consent", "escalate_directory_check", "escalate_human_review"}
)


@dataclass
class BenchRow:
    scenario_id: str
    category: str
    expected_high_stakes: bool
    model: str
    unguarded_answer: str
    rubric_complied: bool
    rubric_refused: bool
    judge_complied: bool | None
    judge_reason: str
    guarded_outcome: str
    guarded_intercepted: bool
    guarded_human_gate: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
