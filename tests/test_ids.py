"""Tests for regrails.ids."""

from __future__ import annotations

import pytest

from regrails.ids import normalize_cfr_id, sha256_hex, slugify_rule_id


class TestNormalizeCfrId:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("34 CFR 99.31", "34-CFR-99.31"),
            ("34 C.F.R. 99.31", "34-CFR-99.31"),
            ("34 C.F.R. § 99.31", "34-CFR-99.31"),
            ("34 CFR § 99.31", "34-CFR-99.31"),
            ("34cfr99.31", "34-CFR-99.31"),
            ("34-cfr-99.31", "34-CFR-99.31"),
            ("34_CFR_99.31", "34-CFR-99.31"),
            ("  34 CFR 99.30  ", "34-CFR-99.30"),
            ("34 CFR 99.31(a)(1)", "34-CFR-99.31.A.1"),
            ("34 CFR 99.31(a)(1)(i)(B)", "34-CFR-99.31.A.1.I.B"),
            ("34 C.F.R. § 99.37(a)(2)", "34-CFR-99.37.A.2"),
        ],
    )
    def test_canonicalizes(self, raw: str, expected: str) -> None:
        assert normalize_cfr_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "not a citation", "CFR 99.31", "34 99.31"])
    def test_rejects_garbage(self, raw: str) -> None:
        with pytest.raises(ValueError):
            normalize_cfr_id(raw)

    def test_rejects_empty_parens(self) -> None:
        with pytest.raises(ValueError):
            normalize_cfr_id("34 CFR 99.31()")


class TestSlugifyRuleId:
    def test_basic(self) -> None:
        assert slugify_rule_id("ferpa", "99.31", "A1") == "FERPA-99.31-A1"

    def test_strips_cfr_prefix(self) -> None:
        assert slugify_rule_id("FERPA", "34-CFR-99.31", 3) == "FERPA-99.31-3"

    def test_upper_cases_ordinal(self) -> None:
        assert slugify_rule_id("FERPA", "99.30", "b") == "FERPA-99.30-B"

    @pytest.mark.parametrize(
        ("framework", "section", "ordinal"),
        [("", "99.31", "A"), ("FERPA", "", "A"), ("FERPA", "99.31", "")],
    )
    def test_rejects_empty(self, framework: str, section: str, ordinal: str) -> None:
        with pytest.raises(ValueError):
            slugify_rule_id(framework, section, ordinal)

    def test_rejects_unsafe_chars(self) -> None:
        # underscores aren't in the safe charset for slugs (we use hyphens only)
        with pytest.raises(ValueError):
            slugify_rule_id("FERPA", "99.31", "A_1")


class TestSha256Hex:
    def test_known_value(self) -> None:
        # SHA-256 of empty string
        assert sha256_hex("") == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_utf8_handling(self) -> None:
        # Smiley + accented chars to make sure UTF-8 encoding is consistent
        assert len(sha256_hex("Schön 🌍")) == 64

    def test_deterministic(self) -> None:
        assert sha256_hex("hello") == sha256_hex("hello")
