"""Rule-to-scenario coverage / traceability matrix.

Runs the deterministic engine over the golden scenario corpus and reports, for
every encoded rule, which scenarios exercise it (rule.id appears in the
decision's ``matched_rules``). Rules touched by zero scenarios are flagged — the
matrix makes coverage *and gaps* visible at a glance, which is the honest way to
present a POC's partial coverage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .encode import flatten_rules, load_all_sections
from .guardrail import ConsultationRequest, decide
from .models import Rule

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = _PROJECT_ROOT / "tests" / "golden"


def load_golden(golden_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load all golden scenarios from ``tests/golden/*.jsonl``."""
    golden_dir = golden_dir or GOLDEN_DIR
    scenarios: list[dict[str, Any]] = []
    if not golden_dir.exists():
        return scenarios
    for f in sorted(golden_dir.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                scenarios.append(json.loads(line))
    return scenarios


def build_matrix(
    golden_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[Rule]]:
    """Return (rows, scenarios, rules). Each row maps a rule to the scenarios it touches."""
    rules = flatten_rules(load_all_sections())
    scenarios = load_golden(golden_dir)

    touched: dict[str, set[str]] = {r.id: set() for r in rules}
    for sc in scenarios:
        decision = decide(ConsultationRequest(**sc["consultation"]), rules)
        for rid in decision.matched_rules:
            touched.setdefault(rid, set()).add(sc["scenario_id"])

    rows: list[dict[str, Any]] = []
    for r in rules:
        ids = sorted(touched.get(r.id, set()))
        rows.append(
            {
                "rule_id": r.id,
                "framework": r.framework,
                "section": r.section_id,
                "risk_tier": r.risk_tier or "-",
                "n_scenarios": len(ids),
                "scenarios": ids,
            }
        )
    return rows, scenarios, rules


def to_markdown(rows: list[dict[str, Any]], scenarios: list[dict[str, Any]], rules: list[Rule]) -> str:
    """Render the coverage matrix as Markdown."""
    n_rules = len(rules)
    n_scen = len(scenarios)
    covered = sum(1 for r in rows if r["n_scenarios"] > 0)
    uncovered = [r for r in rows if r["n_scenarios"] == 0]

    lines: list[str] = []
    lines.append("# RegRails — rule-to-scenario coverage matrix")
    lines.append("")
    lines.append(
        f"_{covered}/{n_rules} encoded rules are exercised by at least one of "
        f"{n_scen} golden scenarios. This is a proof-of-concept: partial coverage is "
        f"expected and the gaps below are intentional and visible._"
    )
    lines.append("")
    lines.append("| Rule | Framework | Section | Risk | # scenarios | Scenarios |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for r in rows:
        scen = ", ".join(r["scenarios"]) if r["scenarios"] else "_(none — gap)_"
        lines.append(
            f"| `{r['rule_id']}` | {r['framework']} | `{r['section']}` | "
            f"{r['risk_tier']} | {r['n_scenarios']} | {scen} |"
        )
    lines.append("")
    if uncovered:
        lines.append(f"## Coverage gaps ({len(uncovered)} rules with no scenario)")
        lines.append("")
        for r in uncovered:
            lines.append(f"- `{r['rule_id']}` ({r['section']}) — no golden scenario exercises it yet.")
        lines.append("")
    return "\n".join(lines)
