"""Anti-drift data pipeline: dump RegRails' OWN package data to static JSON.

The RegRails web platform reads these generated files instead of re-implementing
any of the engine in TypeScript: six deterministic JSON files plus the
``provenance-sample.jsonl`` hash chain. Because every file is generated *from the
installed ``regrails`` package* — the same loaders, the same OSCAL/SARIF emitters,
the same ``regrails.bench.report`` statistics, and the same ``audit.append_decision``
hash-chaining the CLI uses — the website can never drift from the CLI. A committed
copy lives at ``web/public/data/``; the ``tests/test_web_data_parity.py`` gate
fails CI if a fresh regeneration differs, so a stale website is impossible to merge.

Determinism: every file is serialised with
``json.dumps(obj, indent=2, ensure_ascii=True, sort_keys=True)`` and all volatile
fields (wall-clock ``last-modified`` / ``retrieved_at`` / per-decision UUIDs and
timestamps) are stripped before serialisation, so two runs are byte-identical.

Usage::

    python scripts/gen_web_data.py web/public/data
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ``regrails`` ships a ``py.typed`` marker, so it type-checks as a typed package.
from regrails import __version__
from regrails.audit import append_decision
from regrails.bench import INTERCEPT_OUTCOMES, BenchRow
from regrails.bench.judge import JUDGE_MODEL_DEFAULT
from regrails.bench.report import aggregate, wilson
from regrails.coverage import build_matrix
from regrails.encode import load_all_rules, load_all_sections
from regrails.guardrail import ConsultationRequest, decide
from regrails.models import RegulationSection, Rule
from regrails.oscal import build_catalog
from regrails.sarif import to_sarif

# Repo root is two levels up from this file (``<root>/scripts/gen_web_data.py``).
_ROOT = Path(__file__).resolve().parent.parent
_BENCH = _ROOT / "bench"
_DOCS = _ROOT / "docs"
_RESULTS = _BENCH / "results.jsonl"
_SCENARIOS = _BENCH / "scenarios.heldout.jsonl"

_OUTPUT_FILES = (
    "rules.json",
    "coverage.json",
    "eval.json",
    "oscal.json",
    "sarif.json",
    "methodology.json",
    "provenance-sample.jsonl",
)

# Fixed decision dicts for the committed provenance hash-chain sample. These exact
# dicts (in this exact order) are what ``append_decision`` hashes; changing any
# value or order would change every downstream ``record_hash`` and the committed
# ``web/public/data/provenance-sample.jsonl``. The deterministic generation here
# is what finally PINS that hand-checked sample to a pipeline (no field is volatile,
# so two runs are byte-identical), so ``test_web_data_parity`` now guards it too.
_PROVENANCE_SAMPLE_DECISIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "demo-1",
        "outcome": "allow",
        "framework": "FERPA",
        "risk_tier": "low",
        "query": "What are the library hours tonight?",
    },
    {
        "id": "demo-2",
        "outcome": "escalate_human_review",
        "framework": "Title IV",
        "risk_tier": "high",
        "query": "I defaulted on a loan; am I still eligible for aid?",
    },
    {
        "id": "demo-3",
        "outcome": "block",
        "framework": "FERPA",
        "risk_tier": "medium",
        "query": "Email me Jane Doe full transcript.",
    },
)

# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _dumps(obj: Any) -> str:
    """The one canonical, deterministic JSON encoding used for every file."""
    return json.dumps(obj, indent=2, ensure_ascii=True, sort_keys=True)


def _write(out_dir: Path, name: str, obj: Any) -> None:
    (out_dir / name).write_text(_dumps(obj) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# rules.json
# ---------------------------------------------------------------------------


def _human_gate(rule: Rule) -> bool:
    """A rule forces the human gate when its severity escalates or its tier is high."""
    return bool(rule.severity == "escalate" or rule.risk_tier == "high")


def build_rules(sections: list[RegulationSection]) -> dict[str, Any]:
    """Every encoded rule with its framework, citation, tier, gate flag, and the
    verbatim CFR section text + section hash it derives from."""
    section_by_id = {s.id: s for s in sections}
    rules: list[dict[str, Any]] = []
    for section in sections:
        for rule in section.rules:
            host = section_by_id[rule.section_id]
            rules.append(
                {
                    "id": rule.id,
                    "framework": rule.framework,
                    "section_id": rule.section_id,
                    "citation": rule.citation.source_section,
                    "citation_url": rule.citation.source_url,
                    "source_quote": rule.citation.source_quote,
                    "rule_type": rule.rule_type,
                    "severity": rule.severity,
                    "risk_tier": rule.risk_tier,
                    "human_gate": _human_gate(rule),
                    "text": rule.text,
                    "rationale": rule.rationale,
                    "section_title": host.title,
                    "section_text": host.full_text,
                    "section_hash": host.full_text_hash,
                }
            )
    rules.sort(key=lambda r: (str(r["framework"]), str(r["section_id"]), str(r["id"])))
    return {"rules": rules}


# ---------------------------------------------------------------------------
# coverage.json
# ---------------------------------------------------------------------------


def _gap_rationales() -> dict[str, str]:
    """Per-gap rationale parsed from METHODOLOGY.md section 4 (richer than the
    generic COVERAGE.md line, e.g. ``section 99.30 - electronic-consent validity``)."""
    out: dict[str, str] = {}
    path = _DOCS / "METHODOLOGY.md"
    if not path.exists():
        return out
    pat = re.compile(r"^-\s+`(?P<id>[A-Za-z0-9.\-]+)`\s*\((?P<why>[^)]*)\)", re.MULTILINE)
    for m in pat.finditer(path.read_text(encoding="utf-8")):
        out[m.group("id")] = m.group("why").strip()
    return out


def build_coverage() -> dict[str, Any]:
    """The 31/37 rule-to-scenario matrix plus the 6 uncovered gap IDs + rationale.

    The matrix is rebuilt live by ``regrails.coverage.build_matrix`` (it runs the
    deterministic engine over the golden corpus), so it is the source of truth;
    the gap rationale text is parsed from METHODOLOGY.md / COVERAGE.md."""
    rows, scenarios, rules = build_matrix()
    n_rules = len(rules)
    n_covered = sum(1 for r in rows if r["n_scenarios"] > 0)
    rationales = _gap_rationales()
    generic = "no golden scenario exercises it yet"

    gaps = [
        {
            "rule_id": r["rule_id"],
            "framework": r["framework"],
            "section": r["section"],
            "rationale": rationales.get(str(r["rule_id"]), generic),
        }
        for r in rows
        if r["n_scenarios"] == 0
    ]
    gaps.sort(key=lambda g: str(g["rule_id"]))

    matrix = [
        {
            "rule_id": r["rule_id"],
            "framework": r["framework"],
            "section": r["section"],
            "risk_tier": r["risk_tier"],
            "n_scenarios": r["n_scenarios"],
            "scenarios": r["scenarios"],
        }
        for r in rows
    ]
    matrix.sort(key=lambda r: (str(r["framework"]), str(r["section"]), str(r["rule_id"])))

    return {
        "n_rules": n_rules,
        "n_covered": n_covered,
        "n_gaps": len(gaps),
        "n_golden_scenarios": len(scenarios),
        "matrix": matrix,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# eval.json
# ---------------------------------------------------------------------------


def _complied(r: BenchRow) -> bool:
    return bool(r.judge_complied if r.judge_complied is not None else r.rubric_complied)


def build_eval_section() -> dict[str, Any]:
    """Aggregate ``bench/results.jsonl`` via ``regrails.bench.report`` helpers.

    Reuses ``aggregate`` (Wilson CIs + Cohen's kappa, per model) and ``wilson``
    for the per-scenario rates; the engine outcome is deterministic per scenario,
    so the headline benign/intercept counts come straight off one model's rows.
    Scenario metadata (the CFR basis, the note, the expected stakes) is joined in
    from ``scenarios.heldout.jsonl``."""
    rows = [BenchRow(**r) for r in _load_jsonl(_RESULTS)]
    scen_meta = {s["id"]: s for s in _load_jsonl(_SCENARIOS)}
    agg = aggregate(rows)

    # Per-model block: pull the report's numbers + format the Wilson CI tuple.
    models: list[dict[str, Any]] = []
    for model_id in sorted(agg["models"]):
        s = agg["models"][model_id]
        point, lo, hi = s["unguarded_comply_rate"]
        models.append(
            {
                "model": model_id,
                "n_high_stakes": s["n_high_stakes"],
                "unguarded_complied": s["unguarded_complied"],
                "unguarded_comply_rate": point,
                "unguarded_comply_ci_low": lo,
                "unguarded_comply_ci_high": hi,
                "guarded_intercepted": s["guarded_intercepted"],
                "n_low_stakes": s["n_low_stakes"],
                "unguarded_over_refused": s["unguarded_over_refused"],
                "guarded_allowed": s["guarded_allowed"],
            }
        )

    # Per-scenario block: engine decision (constant across models) + how often the
    # unguarded models complied / refused on it, + the scenario's metadata.
    by_scenario: dict[str, list[BenchRow]] = defaultdict(list)
    for r in rows:
        by_scenario[r.scenario_id].append(r)

    scenarios: list[dict[str, Any]] = []
    for sid in sorted(by_scenario):
        srows = by_scenario[sid]
        first = srows[0]
        meta = scen_meta.get(sid, {})
        scenarios.append(
            {
                "scenario_id": sid,
                "category": first.category,
                "expected_high_stakes": first.expected_high_stakes,
                "cfr_basis": meta.get("cfr_basis", ""),
                "note": meta.get("note", ""),
                "query": meta.get("query", ""),
                "guarded_outcome": first.guarded_outcome,
                "guarded_intercepted": first.guarded_intercepted,
                "guarded_human_gate": first.guarded_human_gate,
                "n_models": len(srows),
                "n_unguarded_complied": sum(1 for r in srows if _complied(r)),
                "n_unguarded_refused": sum(1 for r in srows if r.rubric_refused),
            }
        )

    # Headline: deterministic engine outcomes, deduped to one row per scenario.
    engine_by_sid = {sid: by_scenario[sid][0] for sid in by_scenario}
    high_stakes = [r for r in engine_by_sid.values() if r.expected_high_stakes]
    benign = [r for r in engine_by_sid.values() if not r.expected_high_stakes]
    hs_intercepted = [r for r in high_stakes if r.guarded_intercepted]
    benign_allowed = [r for r in benign if not r.guarded_intercepted]

    # Disagreements: independently-labelled high-stakes that the engine did NOT
    # intercept (reported, not hidden) - ho-07 / ho-08 in the bundled corpus.
    disagreements = [
        {
            "scenario_id": r.scenario_id,
            "guarded_outcome": r.guarded_outcome,
            "cfr_basis": scen_meta.get(r.scenario_id, {}).get("cfr_basis", ""),
            "note": scen_meta.get(r.scenario_id, {}).get("note", ""),
        }
        for r in sorted(high_stakes, key=lambda r: r.scenario_id)
        if not r.guarded_intercepted
    ]

    kappa = agg["judge_rubric_kappa"]
    return {
        "judge_model": JUDGE_MODEL_DEFAULT,
        "intercept_outcomes": sorted(INTERCEPT_OUTCOMES),
        "n_rows": agg["n_rows"],
        "n_judged": agg["n_judged"],
        "n_scenarios": len(by_scenario),
        "judge_rubric_kappa": kappa,
        "headline": {
            "benign_allowed": len(benign_allowed),
            "benign_total": len(benign),
            "high_stakes_intercepted": len(hs_intercepted),
            "high_stakes_total": len(high_stakes),
            # Pooled high-stakes unguarded-comply rate across all rows, with CI.
            "pooled_unguarded_comply": _pooled_comply(rows),
        },
        "models": models,
        "scenarios": scenarios,
        "disagreements": disagreements,
    }


def _pooled_comply(rows: list[BenchRow]) -> dict[str, float]:
    """Pooled (all-model) unguarded high-stakes comply rate with a Wilson CI."""
    hs = [r for r in rows if r.expected_high_stakes]
    k = sum(1 for r in hs if _complied(r))
    point, lo, hi = wilson(k, len(hs))
    return {"k": k, "n": len(hs), "rate": point, "ci_low": lo, "ci_high": hi}


# ---------------------------------------------------------------------------
# oscal.json
# ---------------------------------------------------------------------------


def build_oscal(sections: list[RegulationSection]) -> dict[str, Any]:
    """``oscal.build_catalog`` output with the volatile ``last-modified`` wall-clock
    stripped so the committed file is byte-stable (UUIDs are uuid5-deterministic)."""
    catalog: dict[str, Any] = build_catalog(sections)
    catalog["catalog"]["metadata"].pop("last-modified", None)
    return catalog


# ---------------------------------------------------------------------------
# sarif.json
# ---------------------------------------------------------------------------


def _sample_decisions(rules: list[Rule]) -> list[Any]:
    """A representative spread of decisions - a FERPA block, a directory escalation,
    a Title IV high-stakes human-review, a benign aid explainer, and an
    out-of-scope - so the SARIF log shows every level the emitter produces."""
    requests = [
        ConsultationRequest(
            query="Read me back Marcus Bell's GPA and fall grades.",
            topic="disclosure",
            requester_role="school_official",
            data_requested=["gpa", "grades"],
        ),
        ConsultationRequest(
            query="Confirm whether Janelle Ortiz is enrolled and her major.",
            topic="disclosure",
            requester_role="third_party",
            purpose="directory_lookup",
            data_requested=["enrollment_status", "major"],
        ),
        ConsultationRequest(
            query="Student defaulted on a loan - are they still aid-eligible?",
            topic="aid_status",
            aid_determination_requested=True,
            student_in_default=True,
        ),
        ConsultationRequest(
            query="What does being on SAP warning mean for my aid?",
            topic="aid_status",
            sap_status="on_warning",
        ),
        ConsultationRequest(
            query="What are the library's opening hours this weekend?",
            topic="other",
        ),
    ]
    return [decide(req, rules) for req in requests]


def build_sarif(rules: list[Rule]) -> dict[str, Any]:
    """``sarif.to_sarif`` over a fixed sample of engine decisions. The emitter
    embeds no timestamps, so the output is deterministic."""
    log: dict[str, Any] = to_sarif(_sample_decisions(rules))
    return log


# ---------------------------------------------------------------------------
# methodology.json
# ---------------------------------------------------------------------------


def _split_markdown_sections(text: str) -> tuple[str, list[dict[str, str]]]:
    """Split a Markdown doc into its H1 title + a list of ``## heading`` sections.

    Content above the first ``##`` (after the H1) is captured as a synthetic
    ``Overview`` section so no prose is dropped."""
    lines = text.splitlines()
    title = ""
    sections: list[dict[str, str]] = []
    current_heading: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if current_heading is None and not any(line.strip() for line in buf):
            return
        heading = current_heading if current_heading is not None else "Overview"
        sections.append({"heading": heading, "body_md": "\n".join(buf).strip()})

    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip()
            buf = []
            continue
        buf.append(line)
    flush()
    return title, sections


def build_methodology() -> dict[str, Any]:
    """Parse METHODOLOGY.md (title + sections) and append COVERAGE.md's sections,
    each tagged with its source doc so the website can group them."""
    meth_path = _DOCS / "METHODOLOGY.md"
    cov_path = _DOCS / "COVERAGE.md"

    title, sections_raw = _split_markdown_sections(meth_path.read_text(encoding="utf-8"))
    sections: list[dict[str, str]] = [{**s, "source": "METHODOLOGY.md"} for s in sections_raw]

    if cov_path.exists():
        _cov_title, cov_sections = _split_markdown_sections(cov_path.read_text(encoding="utf-8"))
        sections.extend({**s, "source": "COVERAGE.md"} for s in cov_sections)

    return {"title": title, "sections": sections}


# ---------------------------------------------------------------------------
# provenance-sample.jsonl
# ---------------------------------------------------------------------------


def build_provenance_sample(out_dir: Path) -> Path:
    """Deterministically (re)build the provenance hash-chain sample via the package.

    Writes ``provenance-sample.jsonl`` into ``out_dir`` by feeding the fixed
    ``_PROVENANCE_SAMPLE_DECISIONS`` through ``regrails.audit.append_decision`` — the
    SAME hash-chaining the CLI uses — so the website's "tamper-evident provenance"
    sample is a true projection of the engine, not a hand-written artifact validated
    by nothing. The decisions carry no timestamps/UUIDs, so the output is byte-stable.

    ``append_decision`` *appends*, so any pre-existing file is removed first to keep
    a regeneration in place idempotent. Returns the written path.
    """
    sink = out_dir / "provenance-sample.jsonl"
    if sink.exists():
        sink.unlink()
    for decision in _PROVENANCE_SAMPLE_DECISIONS:
        append_decision(decision, sink)
    return sink


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_web_data(out_dir: Path) -> None:
    """Write the static data files the RegRails website consumes into ``out_dir``.

    Six deterministic JSON files plus the ``provenance-sample.jsonl`` hash chain.
    Pulls everything from the installed ``regrails`` package + the committed bench
    data + docs, so the website is a pure projection of the CLI's own data."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load the encoded corpus once and thread it through the rule/OSCAL/SARIF builders.
    sections = load_all_sections()
    rules = load_all_rules()

    _write(out_dir, "rules.json", build_rules(sections))
    _write(out_dir, "coverage.json", build_coverage())
    _write(out_dir, "eval.json", build_eval_section())
    _write(out_dir, "oscal.json", build_oscal(sections))
    _write(out_dir, "sarif.json", build_sarif(rules))
    _write(out_dir, "methodology.json", build_methodology())

    # The provenance hash-chain sample is emitted via the package's own
    # ``append_decision`` (not the JSON ``_write`` helper) so its bytes match what
    # the CLI ``regrails audit`` would produce, and so it is now pipeline-pinned.
    build_provenance_sample(out_dir)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out_dir = Path(args[0]) if args else (_ROOT / "web" / "public" / "data")
    build_web_data(out_dir)
    msg = f"Wrote {len(_OUTPUT_FILES)} web-data files to {out_dir} (regrails v{__version__})\n"
    sys.stdout.write(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
