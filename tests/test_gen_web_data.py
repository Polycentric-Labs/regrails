"""Unit tests for the anti-drift web-data generator.

Builds the six static JSON files into a temp dir and asserts their shape: all
files exist, parse as JSON, and the headline invariants hold (37 rules across the
two bundled frameworks, 31/37 coverage, the benign/intercept eval headline).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gen_web_data import build_web_data  # noqa: E402

_EXPECTED_FILES = (
    "rules.json",
    "coverage.json",
    "eval.json",
    "oscal.json",
    "sarif.json",
    "methodology.json",
)


def _build(tmp_path: Path) -> dict[str, object]:
    """Build into ``tmp_path`` and return parsed JSON keyed by file *stem*
    (``oscal``, ``sarif``, ...), so assertions index by the short name."""
    build_web_data(tmp_path)
    out: dict[str, object] = {}
    for name in _EXPECTED_FILES:
        p = tmp_path / name
        assert p.exists(), f"{name} was not written"
        out[Path(name).stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def test_all_six_files_exist_and_are_valid_json(tmp_path: Path) -> None:
    data = _build(tmp_path)
    assert set(data.keys()) == {Path(n).stem for n in _EXPECTED_FILES}


def test_rules_count_is_thirty_seven_and_two_frameworks(tmp_path: Path) -> None:
    data = _build(tmp_path)
    rules = data["rules"]
    assert isinstance(rules, dict)
    rule_list = rules["rules"]
    assert isinstance(rule_list, list)
    assert len(rule_list) == 37
    frameworks = {r["framework"] for r in rule_list}
    assert frameworks == {"FERPA", "Title IV"}


def test_each_rule_carries_the_required_fields(tmp_path: Path) -> None:
    data = _build(tmp_path)
    rule_list = data["rules"]["rules"]  # type: ignore[index]
    required = {
        "id",
        "framework",
        "citation",
        "risk_tier",
        "human_gate",
        "section_text",
        "section_hash",
    }
    for r in rule_list:
        assert required <= set(r.keys()), f"missing fields on {r.get('id')}: {required - set(r.keys())}"
        # Section hash is a 64-char hex SHA-256 of the verbatim CFR section text.
        assert len(r["section_hash"]) == 64
        assert r["section_text"].strip()


def test_coverage_matrix_is_31_of_37_with_six_gaps(tmp_path: Path) -> None:
    data = _build(tmp_path)
    cov = data["coverage"]
    assert isinstance(cov, dict)
    assert cov["n_rules"] == 37
    assert cov["n_covered"] == 31
    assert len(cov["gaps"]) == 6
    for gap in cov["gaps"]:
        assert gap["rule_id"]
        assert gap["rationale"]


def test_eval_headline_matches_the_published_numbers(tmp_path: Path) -> None:
    data = _build(tmp_path)
    ev = data["eval"]
    assert isinstance(ev, dict)
    headline = ev["headline"]
    assert headline["benign_allowed"] == 7
    assert headline["benign_total"] == 7
    assert headline["high_stakes_intercepted"] == 15
    assert headline["high_stakes_total"] == 17
    # The two reported label-vs-engine disagreements.
    disagreement_ids = {d["scenario_id"] for d in ev["disagreements"]}
    assert disagreement_ids == {"ho-07", "ho-08"}
    # Per-model + per-scenario breakdowns are present.
    assert ev["models"]
    assert ev["scenarios"]


def test_oscal_catalog_shape(tmp_path: Path) -> None:
    data = _build(tmp_path)
    oscal = data["oscal"]
    assert isinstance(oscal, dict)
    cat = oscal["catalog"]
    assert cat["metadata"]["oscal-version"] == "1.1.2"
    controls = [c for g in cat["groups"] for c in g["controls"]]
    assert len(controls) == 37
    # The volatile last-modified field must be normalised out for determinism.
    assert "last-modified" not in cat["metadata"]


def test_sarif_log_shape(tmp_path: Path) -> None:
    data = _build(tmp_path)
    sarif = data["sarif"]
    assert isinstance(sarif, dict)
    assert sarif["version"] == "2.1.0"
    results = sarif["runs"][0]["results"]
    assert len(results) >= 1


def test_methodology_has_title_and_sections(tmp_path: Path) -> None:
    data = _build(tmp_path)
    meth = data["methodology"]
    assert isinstance(meth, dict)
    assert meth["title"]
    assert isinstance(meth["sections"], list)
    assert len(meth["sections"]) >= 2
    for s in meth["sections"]:
        assert s["heading"]
        assert "body_md" in s


def test_output_is_byte_stable_across_two_builds(tmp_path: Path) -> None:
    """Re-running the generator must produce identical bytes (the anti-drift core)."""
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_web_data(first)
    build_web_data(second)
    for name in _EXPECTED_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes(), f"{name} not byte-stable"
