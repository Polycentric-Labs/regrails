"""End-to-end AI-advisor guardrail demo — ``python -m regrails.demo``.

Loads scenarios from ``demo/queries.yaml`` and runs each through:

    user query
        -> ConsultationRequest (structured tool-call)
        -> guardrail.decide()        (deterministic rule engine: FERPA + Title IV)
        -> hash-chained decision log (tamper-evident provenance)
        -> llm.advisor_render()      (LLM renders the user-facing reply only)
        -> record to demo/recorded-runs/<id>.json

Modes:
    python -m regrails.demo --all
        Run every scenario via the live LLM, write recorded-runs + a hash-chained
        decisions log, and print a side-by-side markdown table.
    python -m regrails.demo --replay <path>
        Re-emit a previously-recorded transcript (works WITHOUT an API key).
    python -m regrails.demo --all --scenario <id>
        Run a single scenario.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml

from .audit import append_decision
from .encode import load_all_rules
from .guardrail import ConsultationRequest, decide

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
QUERIES_FILE = PROJECT_ROOT / "demo" / "queries.yaml"
RECORDED_DIR = PROJECT_ROOT / "demo" / "recorded-runs"
DECISIONS_CHAIN = RECORDED_DIR / "decisions.chain.jsonl"


def _load_scenarios() -> list[dict[str, Any]]:
    raw = cast(dict[str, Any], yaml.safe_load(QUERIES_FILE.read_text(encoding="utf-8")))
    return cast(list[dict[str, Any]], raw.get("scenarios", []))


def _run_one(scenario: dict[str, Any], rules: list[Any]) -> dict[str, Any]:
    from .llm import advisor_render  # local import: keeps --replay free of httpx/LLM

    query = scenario["query"]
    consultation = ConsultationRequest(query=query, **scenario.get("consultation", {}))
    decision = decide(consultation, rules, model="")
    expected = scenario.get("expected_outcome")
    if expected and decision.outcome != expected:
        sys.stderr.write(
            f"WARNING scenario {scenario['id']}: expected outcome={expected!r} "
            f"but got {decision.outcome!r}\n"
        )

    decision_dict = decision.model_dump(mode="json")
    record_hash = append_decision(decision_dict, DECISIONS_CHAIN)

    reply, model_used = advisor_render(query=query, decision=decision)
    return {
        "scenario_id": scenario["id"],
        "title": scenario.get("title", ""),
        "query": query,
        "consultation": consultation.model_dump(mode="json"),
        "decision": decision_dict,
        "record_hash": record_hash,
        "advisor_reply": reply,
        "advisor_model": model_used,
        "rendered_at": datetime.now(UTC).isoformat(),
    }


def _persist(record: dict[str, Any]) -> Path:
    RECORDED_DIR.mkdir(parents=True, exist_ok=True)
    target = RECORDED_DIR / f"{record['scenario_id']}.json"
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return target


def render_table(records: list[dict[str, Any]]) -> str:
    """Render the side-by-side markdown table (returned, not just printed)."""
    lines: list[str] = []
    lines.append("# RegRails demo — guardrail decisions across FERPA + Title IV")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(UTC).isoformat()}_")
    lines.append("")
    lines.append("| # | Framework | Query | Outcome | Risk | Human gate | Citations | Advisor reply |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(records, 1):
        d = r["decision"]
        q = r["query"].replace("|", "\\|")
        outcome = d["outcome"]
        risk = d.get("risk_tier", "-")
        gate = "YES" if d.get("human_gate_required") else "-"
        cites = ", ".join(d.get("citations_emitted", []))
        reply = r["advisor_reply"].replace("\n", " ").replace("|", "\\|").strip()
        if len(reply) > 240:
            reply = reply[:235] + "..."
        lines.append(
            f"| {i} | {d.get('framework', '-')} | {q} | **{outcome}** | {risk} | {gate} | "
            f"{cites} | {reply} |"
        )
    lines.append("")
    return "\n".join(lines)


def _replay(path: Path) -> None:
    if path.is_dir():
        records = [
            json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(path.glob("*.json"))
        ]
    else:
        records = [json.loads(path.read_text(encoding="utf-8"))]
    print(render_table(records))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regrails.demo", description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="Run every scenario via the live LLM.")
    g.add_argument("--replay", metavar="PATH", type=Path, help="Replay a recorded JSON or dir.")
    parser.add_argument("--scenario", default=None, help="(With --all) run only this scenario id.")
    args = parser.parse_args(argv)

    if args.replay:
        _replay(args.replay)
        return 0

    rules = load_all_rules()
    scenarios = _load_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            sys.stderr.write(f"no such scenario: {args.scenario}\n")
            return 2

    # Fresh hash chain for a full run.
    if not args.scenario:
        RECORDED_DIR.mkdir(parents=True, exist_ok=True)
        DECISIONS_CHAIN.unlink(missing_ok=True)

    records: list[dict[str, Any]] = []
    for sc in scenarios:
        print(f"  running {sc['id']} ...", file=sys.stderr)
        record = _run_one(sc, rules)
        path = _persist(record)
        print(f"    saved {path.name} (model={record['advisor_model']})", file=sys.stderr)
        records.append(record)

    print(render_table(records))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
