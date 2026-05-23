"""RegRails core data models (Pydantic v2).

The shape mirrors Evidentia's ``EvidentiaModel`` base (see
``packages/evidentia-core/src/evidentia_core/models/catalog.py``) — ``extra="forbid"``,
ISO 8601 timestamps, and string-valued enums for stable JSON.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .ids import sha256_hex

# ---------------------------------------------------------------------------
# Literals (closed sets — POC keeps these inline rather than as Enum classes)
# ---------------------------------------------------------------------------

RuleType = Literal["prohibition", "permission", "consent_required", "exception", "definition"]
Severity = Literal["block", "escalate", "warn"]
Outcome = Literal["allow", "block", "escalate_consent", "escalate_directory_check"]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class RegRailsModel(BaseModel):
    """Shared base — ``extra="forbid"`` catches typo'd fields at load time."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Citation
# ---------------------------------------------------------------------------


class Citation(RegRailsModel):
    """Provenance for a single Rule — points back to the source CFR text."""

    source_url: str = Field(..., description="Canonical eCFR URL for the section")
    source_section: str = Field(..., description="Canonical section id, e.g. '34-CFR-99.31'")
    source_quote: str = Field(..., description="Verbatim CFR text this rule encodes")
    source_hash: str = Field(..., description="SHA-256 (hex) of source_quote, UTF-8 encoded")
    retrieved_at: datetime = Field(default_factory=_utcnow)
    publication_date: str | None = Field(
        default=None,
        description="eCFR publication date (e.g. '2026-07-01') if known",
    )

    @field_validator("source_hash")
    @classmethod
    def _validate_sha256_hex(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("source_hash must be a 64-char lower-case hex SHA-256")
        return v.lower()

    @classmethod
    def from_quote(
        cls,
        *,
        source_url: str,
        source_section: str,
        source_quote: str,
        publication_date: str | None = None,
    ) -> Citation:
        """Build a Citation, computing ``source_hash`` from ``source_quote``."""
        return cls(
            source_url=source_url,
            source_section=source_section,
            source_quote=source_quote,
            source_hash=sha256_hex(source_quote),
            publication_date=publication_date,
        )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class Rule(RegRailsModel):
    """A single machine-readable rule derived from a CFR clause."""

    id: str = Field(..., description="e.g. 'FERPA-99.31-A1'")
    section_id: str = Field(..., description="Canonical section, e.g. '34-CFR-99.31'")
    text: str = Field(..., description="Rule statement in operator-readable English")
    rule_type: RuleType
    triggers: list[str] = Field(
        default_factory=list,
        description="Tags like 'disclosure', 'education_record', 'third_party'",
    )
    requires_consent: bool = False
    requires_directory_opt_out_check: bool = False
    requires_legitimate_educational_interest: bool = False
    safe_harbor_conditions: list[str] = Field(default_factory=list)
    citation: Citation
    severity: Severity = "block"
    rationale: str = Field(..., description="1-2 sentence operator-readable why")

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Rule.id cannot be empty")
        return v


# ---------------------------------------------------------------------------
# RegulationSection
# ---------------------------------------------------------------------------


class RegulationSection(RegRailsModel):
    """A whole CFR section bundled with its rules and verbatim source."""

    id: str = Field(..., description="Canonical section id, e.g. '34-CFR-99.31'")
    title: str = Field(..., description="Section heading")
    subpart: str = Field(..., description="Subpart letter, e.g. 'D'")
    full_text: str = Field(..., description="Verbatim CFR text for the whole section")
    full_text_hash: str = Field(..., description="SHA-256 (hex) of full_text")
    rules: list[Rule]
    source_url: str
    retrieved_at: datetime = Field(default_factory=_utcnow)

    @field_validator("full_text_hash")
    @classmethod
    def _validate_sha256_hex(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v.lower()):
            raise ValueError("full_text_hash must be a 64-char lower-case hex SHA-256")
        return v.lower()

    @classmethod
    def from_full_text(
        cls,
        *,
        id: str,
        title: str,
        subpart: str,
        full_text: str,
        rules: list[Rule],
        source_url: str,
    ) -> RegulationSection:
        """Build a RegulationSection, computing ``full_text_hash`` automatically."""
        return cls(
            id=id,
            title=title,
            subpart=subpart,
            full_text=full_text,
            full_text_hash=sha256_hex(full_text),
            rules=rules,
            source_url=source_url,
        )


# ---------------------------------------------------------------------------
# ResearchSnapshot
# ---------------------------------------------------------------------------


class ResearchSnapshot(RegRailsModel):
    """One execution of a research stream against Perplexity Sonar."""

    id: str
    stream_name: str
    query: str
    model: str = Field(..., description="OpenRouter model id, e.g. 'perplexity/sonar-pro'")
    response_text: str
    citations: list[dict[str, str | int | float | None]] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=_utcnow)
    relates_to_rules: list[str] = Field(default_factory=list)
    cost_usd: float | None = None


# ---------------------------------------------------------------------------
# GuardrailDecision
# ---------------------------------------------------------------------------


class GuardrailDecision(RegRailsModel):
    """Audit record for one guardrail invocation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    timestamp: datetime = Field(default_factory=_utcnow)
    matched_rules: list[str] = Field(default_factory=list)
    outcome: Outcome
    llm_response: str = ""
    citations_emitted: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    model: str = Field(default="", description="OpenRouter model id of the advisor LLM")
