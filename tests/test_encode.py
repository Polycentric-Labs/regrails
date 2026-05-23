"""Tests for regrails.encode."""

from __future__ import annotations

from pathlib import Path

import pytest

from regrails.encode import default_paths, flatten_rules, load_sections

# These tests use the bundled YAML + CFR text rather than fixtures so they
# also serve as a smoke-test for the canonical FERPA Subpart D encoding.


def test_load_sections_returns_six_sections() -> None:
    sections = load_sections()
    assert len(sections) == 6
    ids = [s.id for s in sections]
    assert ids == [
        "34-CFR-99.30",
        "34-CFR-99.31",
        "34-CFR-99.32",
        "34-CFR-99.33",
        "34-CFR-99.36",
        "34-CFR-99.37",
    ]


def test_load_sections_yields_twenty_three_rules() -> None:
    sections = load_sections()
    rules = flatten_rules(sections)
    assert len(rules) == 23


def test_each_rule_carries_citation_with_hash() -> None:
    sections = load_sections()
    rules = flatten_rules(sections)
    for rule in rules:
        assert rule.citation.source_quote
        assert len(rule.citation.source_hash) == 64
        assert rule.citation.source_url.startswith("https://www.law.cornell.edu/cfr/text/34/")
        assert rule.citation.source_section.startswith("34-CFR-99.")


def test_full_text_hash_matches_content() -> None:
    from regrails.ids import sha256_hex

    sections = load_sections()
    for section in sections:
        assert section.full_text_hash == sha256_hex(section.full_text)


def test_section_text_actually_starts_with_section_heading() -> None:
    sections = load_sections()
    for section in sections:
        first_line = section.full_text.splitlines()[0].strip()
        assert first_line.startswith("§"), first_line
        # The CFR section number from id (e.g. 99.31) should appear in the heading.
        num = section.id.removeprefix("34-CFR-")
        assert num in first_line


def test_rule_ids_unique_and_well_formed() -> None:
    sections = load_sections()
    ids = [r.id for r in flatten_rules(sections)]
    assert len(ids) == len(set(ids))
    for rule_id in ids:
        assert rule_id.startswith("FERPA-99.")


def test_audit_sink_collects_events(tmp_path: Path) -> None:
    sink = tmp_path / "audit.jsonl"
    sections = load_sections(audit_sink=sink)
    contents = sink.read_text(encoding="utf-8").strip().splitlines()
    # 23 RULE_ENCODED + 6 SECTION_LOADED = 29 events
    assert len(contents) == 29
    rule_events = [line for line in contents if "rule_encoded" in line]
    section_events = [line for line in contents if "section_loaded" in line]
    assert len(rule_events) == 23
    assert len(section_events) == 6
    assert len(sections) == 6  # also confirm normal return value works


def test_missing_yaml_raises(tmp_path: Path) -> None:
    yaml_path = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        load_sections(yaml_path=yaml_path, bundle_path=default_paths()[1])


def test_missing_bundle_raises(tmp_path: Path) -> None:
    bundle = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        load_sections(yaml_path=default_paths()[0], bundle_path=bundle)


def test_yaml_referencing_unknown_section_raises(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text(
        """
metadata: {}
sections:
  - id: 34-CFR-99.99
    title: Phantom section
    subpart: D
    source_url: https://example.test
    rules: []
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing from bundled text"):
        load_sections(yaml_path=bad_yaml, bundle_path=default_paths()[1])
