"""Tests for regrails.models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from regrails.ids import sha256_hex
from regrails.models import (
    Citation,
    GuardrailDecision,
    RegulationSection,
    ResearchSnapshot,
    Rule,
)

SAMPLE_QUOTE = (
    "An educational agency or institution may disclose "
    "personally identifiable information..."
)
SAMPLE_URL = (
    "https://www.ecfr.gov/current/title-34/subtitle-A/part-99/subpart-D/section-99.31"
)


def _citation() -> Citation:
    return Citation.from_quote(
        source_url=SAMPLE_URL,
        source_section="34-CFR-99.31",
        source_quote=SAMPLE_QUOTE,
    )


def _rule() -> Rule:
    return Rule(
        id="FERPA-99.31-A1",
        section_id="34-CFR-99.31",
        text="An LEA may disclose to a school official with legitimate educational interest.",
        rule_type="exception",
        triggers=["disclosure", "school_official"],
        requires_legitimate_educational_interest=True,
        citation=_citation(),
        rationale="§99.31(a)(1) carves out school officials from the consent default.",
    )


class TestCitation:
    def test_from_quote_computes_hash(self) -> None:
        c = _citation()
        assert c.source_hash == sha256_hex(SAMPLE_QUOTE)
        assert len(c.source_hash) == 64

    def test_retrieved_at_is_tz_aware(self) -> None:
        c = _citation()
        assert c.retrieved_at.tzinfo is not None

    def test_rejects_bad_hash(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_url=SAMPLE_URL,
                source_section="34-CFR-99.31",
                source_quote=SAMPLE_QUOTE,
                source_hash="not-a-hex-digest",
            )

    def test_extra_forbid(self) -> None:
        with pytest.raises(ValidationError):
            Citation(
                source_url=SAMPLE_URL,
                source_section="34-CFR-99.31",
                source_quote=SAMPLE_QUOTE,
                source_hash=sha256_hex(SAMPLE_QUOTE),
                spurious_extra="nope",  # type: ignore[call-arg]
            )


class TestRule:
    def test_construction(self) -> None:
        r = _rule()
        assert r.id == "FERPA-99.31-A1"
        assert r.severity == "block"  # default
        assert r.requires_legitimate_educational_interest is True

    def test_rejects_empty_id(self) -> None:
        with pytest.raises(ValidationError):
            Rule(
                id="   ",
                section_id="34-CFR-99.31",
                text="x",
                rule_type="prohibition",
                citation=_citation(),
                rationale="x",
            )

    def test_rule_type_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Rule(
                id="X-1",
                section_id="34-CFR-99.31",
                text="x",
                rule_type="not_a_real_type",  # type: ignore[arg-type]
                citation=_citation(),
                rationale="x",
            )


class TestRegulationSection:
    def test_from_full_text_computes_hash(self) -> None:
        full = "§ 99.30 Under what conditions is prior consent required..."
        s = RegulationSection.from_full_text(
            id="34-CFR-99.30",
            title="Under what conditions is prior consent required",
            subpart="D",
            full_text=full,
            rules=[_rule()],
            source_url=SAMPLE_URL,
        )
        assert s.full_text_hash == sha256_hex(full)

    def test_holds_multiple_rules(self) -> None:
        s = RegulationSection.from_full_text(
            id="34-CFR-99.31",
            title="Conditions for disclosure without consent",
            subpart="D",
            full_text=SAMPLE_QUOTE,
            rules=[_rule(), _rule()],
            source_url=SAMPLE_URL,
        )
        assert len(s.rules) == 2


class TestResearchSnapshot:
    def test_minimal(self) -> None:
        snap = ResearchSnapshot(
            id="stream-1-2026-05-24",
            stream_name="ferpa-ai-ambiguities",
            query="What does the law say?",
            model="perplexity/sonar-pro",
            response_text="The law says many things.",
        )
        assert snap.citations == []
        assert snap.cost_usd is None
        assert snap.fetched_at.tzinfo is not None


class TestGuardrailDecision:
    def test_uuid_default(self) -> None:
        d = GuardrailDecision(query="What's Jane's GPA?", outcome="block")
        assert len(d.id) == 36  # uuid4 string form

    def test_outcome_literal_enforced(self) -> None:
        with pytest.raises(ValidationError):
            GuardrailDecision(query="x", outcome="banana")  # type: ignore[arg-type]

    def test_timestamp_tz_aware(self) -> None:
        before = datetime.now(UTC)
        d = GuardrailDecision(query="x", outcome="allow")
        assert d.timestamp >= before
        assert d.timestamp.tzinfo is not None
