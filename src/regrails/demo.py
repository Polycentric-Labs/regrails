"""End-to-end AI-advisor guardrail demo — ``python -m regrails.demo``.

Loads the 7 scenarios from ``demo/queries.yaml``, runs each through:

    user query
        → ConsultationRequest (structured tool-call)
        → guardrail.decide()              (deterministic rule engine)
        → llm.advisor_render()            (LLM renders the user-facing reply)
        → record { query, decision, reply } to demo/recorded-runs/<id>.json

Modes:

    python -m regrails.demo --all
        Run every scenario fresh against the live LLM, write recorded-runs,
        and emit a side-by-side markdown table to stdout.

    python -m regrails.demo --replay <path>
        Load a previously-recorded transcript and re-emit it. Used by reviewers
        who don't have an OPENROUTER_API_KEY (the canonical demo can still be
        inspected end-to-end).

The ``--all`` mode also accepts a single ``--scenario <id>`` to run one demo,
useful during development.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml

from .encode import flatten_rules, load_sections
from .guardrail import ConsultationRequest, decide
from .llm import advisor_render

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
QUERIES_FILE = PROJECT_ROOT / "demo" / "queries.yaml"
RECORDED_DIR = PROJECT_ROOT / "demo" / "recorded-runs"


def _load_scenarios() -> list[dict[str, Any]]:
    raw = cast(dict[str, Any], yaml.safe_load(QUERIES_FILE.read_text(encoding="utf-8")))
    return cast(list[dict[str, Any]], raw.get("scenarios", []))


def _run_one(
    scenario: dict[str, Any],
    rules: list[Any],
) -> dict[str, Any]:
    query = scenario["query"]
    consultation = ConsultationRequest(query=query, **scenario.get("consultation", {}))
    decision = decide(consultation, rules, model="")
    expected = scenario.get("expected_outcome")
    if expected and decision.outcome != expected:
        sys.stderr.write(
            f"⚠️  scenario {scenario['id']}: expected outcome={expected!r} "
            f"but got {decision.outcome!r}\n"
        )

    reply, model_used = advisor_render(query=query, decision=decision)
    return {
        "scenario_id": scenario["id"],
        "title": scenario.get("title", ""),
        "query": query,
        "consultation": consultation.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
        "advisor_reply": reply,
        "advisor_model": model_used,
        "rendered_at": datetime.now(UTC).isoformat(),
    }


def _persist(record: dict[str, Any]) -> Path:
    RECORDED_DIR.mkdir(parents=True, exist_ok=True)
    target = RECORDED_DIR / f"{record['scenario_id']}.json"
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return target


def _print_table(records: list[dict[str, Any]]) -> None:
    for _i, r in enumerate(records, 1):
        r["query"].replace("|", "\\|")
        r["decision"]["outcome"]
        ", ".join(r["decision"]["citations_emitted"])
        reply = r["advisor_reply"].replace("\n", " ").replace("|", "\\|").strip()
        if len(reply) > 280:
            reply = reply[:275] + "..."


def _replay(path: Path) -> None:
    if path.is_dir():
        records = []
        for f in sorted(path.glob("*.json")):
            records.append(json.loads(f.read_text(encoding="utf-8")))
    else:
        records = [json.loads(path.read_text(encoding="utf-8"))]
    _print_table(records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="regrails.demo", description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="Run every scenario via the live LLM.")
    g.add_argument(
        "--replay",
        metavar="PATH",
        type=Path,
        help="Replay a single recorded-runs JSON (or a directory of them).",
    )
    parser.add_argument(
        "--scenario",
        help="(With --all) run only the scenario with this id.",
        default=None,
    )
    args = parser.parse_args(argv)

    if args.replay:
        _replay(args.replay)
        return 0

    rules = flatten_rules(load_sections())
    scenarios = _load_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s["id"] == args.scenario]
        if not scenarios:
            sys.stderr.write(f"no such scenario: {args.scenario}\n")
            return 2

    records: list[dict[str, Any]] = []
    for sc in scenarios:
        record = _run_one(sc, rules)
        _persist(record)
        records.append(record)

    _print_table(records)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
