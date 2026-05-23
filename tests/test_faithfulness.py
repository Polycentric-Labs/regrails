"""Tests for regrails.faithfulness."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from regrails.encode import load_sections
from regrails.faithfulness import (
    DEFAULT_THRESHOLD,
    _coverage,
    _jaccard,
    _tokenize,
    check_bundled,
    check_rule,
    check_sections,
)
from regrails.ids import sha256_hex
from regrails.models import Citation, RegulationSection, Rule


class TestTokenize:
    def test_lowercases_and_drops_punct(self) -> None:
        assert _tokenize("Hello, World!") == {"hello", "world"}

    def test_empty_returns_empty(self) -> None:
        assert _tokenize("") == set()
        assert _tokenize("...---!!!") == set()

    def test_numbers_are_tokens(self) -> None:
        assert _tokenize("CFR 99.31(a)(1)") == {"cfr", "99", "31", "a", "1"}

    def test_non_ascii_dropped(self) -> None:
        # § is non-ASCII; em-dash too
        assert _tokenize("§ 99.31 — text") == {"99", "31", "text"}


class TestJaccard:
    def test_identical_sets(self) -> None:
        s = {"a", "b", "c"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint_sets(self) -> None:
        assert _jaccard({"a"}, {"b"}) == 0.0

    def test_both_empty(self) -> None:
        assert _jaccard(set(), set()) == 0.0

    def test_partial_overlap(self) -> None:
        # |a∩b|=1 (only 'a'); |a∪b|=3 ({a,b,c}); 1/3
        assert _jaccard({"a", "b"}, {"a", "c"}) == pytest.approx(1 / 3)


class TestCoverage:
    def test_full_coverage(self) -> None:
        assert _coverage({"a", "b"}, {"a", "b", "c", "d"}) == 1.0

    def test_zero_coverage(self) -> None:
        assert _coverage({"x"}, {"a", "b"}) == 0.0

    def test_empty_quote(self) -> None:
        assert _coverage(set(), {"a"}) == 0.0


# ---------------------------------------------------------------------------
# check_rule against synthetic section
# ---------------------------------------------------------------------------


def _make_rule(quote: str) -> tuple[Rule, RegulationSection]:
    full = (
        "§ 99.99 Synthetic test section.\n\n"
        "(a) The quick brown fox jumps over the lazy dog while "
        "an educational agency may not disclose anything spicy without consent."
    )
    citation = Citation.from_quote(
        source_url="https://example.test/cfr/34/99.99",
        source_section="34-CFR-99.99",
        source_quote=quote,
    )
    rule = Rule(
        id="TEST-99.99-1",
        section_id="34-CFR-99.99",
        text="Synthetic rule for testing.",
        rule_type="prohibition",
        triggers=["test"],
        citation=citation,
        rationale="Test rationale.",
    )
    section = RegulationSection(
        id="34-CFR-99.99",
        title="Synthetic test section.",
        subpart="X",
        full_text=full,
        full_text_hash=sha256_hex(full),
        rules=[rule],
        source_url="https://example.test/cfr/34/99.99",
        retrieved_at=datetime.now(UTC),
    )
    return rule, section


class TestCheckRule:
    def test_verbatim_substring_passes(self) -> None:
        rule, section = _make_rule("an educational agency may not disclose")
        result = check_rule(rule, section)
        assert result.passed is True
        assert result.is_substring is True
        assert result.coverage == 1.0

    def test_reordered_words_still_pass_via_coverage(self) -> None:
        rule, section = _make_rule("disclose anything educational agency may not without consent")
        result = check_rule(rule, section)
        assert result.is_substring is False
        assert result.coverage == 1.0  # all tokens are in the section
        assert result.passed is True

    def test_token_not_in_source_fails(self) -> None:
        rule, section = _make_rule("zebras and elephants disclose nothing")
        result = check_rule(rule, section)
        assert result.passed is False
        assert "zebras" in result.missing_tokens
        assert "elephants" in result.missing_tokens


# ---------------------------------------------------------------------------
# Integration: check the actual bundled FERPA encoding
# ---------------------------------------------------------------------------


class TestCheckBundled:
    def test_all_23_rules_pass(self) -> None:
        """The bundled FERPA encoding must pass at the default threshold."""
        report = check_bundled()
        assert report.passed is True, "\n" + report.to_markdown_table()
        assert len(report.results) == 23
        assert report.passed_count == 23

    def test_all_substring_matches(self) -> None:
        """For the POC, every encoded source_quote is meant to be VERBATIM —
        substring containment should hold for every rule."""
        report = check_bundled()
        non_substring = [r for r in report.results if not r.is_substring]
        assert non_substring == [], (
            "Some rules don't have verbatim source_quote substring match:\n"
            + "\n".join(f"  {r.rule_id}: coverage={r.coverage:.3f}" for r in non_substring)
        )

    def test_threshold_lowered_still_passes(self) -> None:
        report = check_bundled(threshold=0.5)
        assert report.passed is True

    def test_threshold_unrealistically_high_does_not_break_substring_path(self) -> None:
        # Substring matches always pass regardless of threshold.
        report = check_bundled(threshold=0.99)
        substring_count = sum(1 for r in report.results if r.is_substring)
        # All substring-true rules still passed
        substring_results = [r for r in report.results if r.is_substring]
        assert all(r.passed for r in substring_results)
        assert substring_count == 23


# ---------------------------------------------------------------------------
# Markdown rendering smoke
# ---------------------------------------------------------------------------


def test_to_markdown_table_renders() -> None:
    sections = load_sections()
    report = check_sections(sections, threshold=DEFAULT_THRESHOLD)
    md = report.to_markdown_table()
    assert "| Rule | Section | substring?" in md
    assert "FERPA-99.30-1" in md
    assert "FERPA-99.37-E" in md
