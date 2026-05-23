"""Load encoded YAML rules + bundled CFR text into RegulationSection objects.

Pairs each YAML rule with the verbatim source text. ``load_sections()`` is the
single public entry point and the input to both the faithfulness gate and the
guardrail engine.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml

from .audit import EventAction, emit_event
from .ids import sha256_hex
from .models import Citation, RegulationSection, Rule

_RULER = "=" * 78
_SECTION_HEADING_RE = re.compile(r"^§\s*(?P<num>\d+(?:\.\d+)*)\s+(?P<title>.+?)\s*$")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_YAML = _PROJECT_ROOT / "data" / "encoded" / "ferpa-subpart-d.yaml"
_DEFAULT_BUNDLE = _PROJECT_ROOT / "data" / "cfr" / "ferpa-subpart-d.txt"


def default_paths() -> tuple[Path, Path]:
    """Return the bundled (yaml_path, bundle_path) used in tests + CLI."""
    return _DEFAULT_YAML, _DEFAULT_BUNDLE


def _slice_bundle_by_section(bundle_text: str) -> dict[str, str]:
    """Split the bundled CFR text into ``{ "99.31": "<full text>", ... }``.

    The bundle is shaped: header comments → ``====`` ruler → ``§ 99.XX Title``
    → section body → next ``====`` ruler → next section, etc.
    """
    chunks = bundle_text.split(_RULER)
    out: dict[str, str] = {}
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.split("\n", 1)
        heading_match = _SECTION_HEADING_RE.match(lines[0].strip())
        if not heading_match:
            continue
        num = heading_match.group("num")
        out[num] = chunk  # store FULL chunk including heading + body + authority
    return out


def _section_num_from_id(section_id: str) -> str:
    """Extract ``99.31`` from ``34-CFR-99.31``."""
    m = re.match(r"^\d+-CFR-(?P<num>\d+(?:\.\d+)*)$", section_id)
    if not m:
        raise ValueError(f"unrecognized section id: {section_id!r}")
    return m.group("num")


def load_sections(
    yaml_path: Path | None = None,
    bundle_path: Path | None = None,
    *,
    audit_sink: Path | None = None,
) -> list[RegulationSection]:
    """Load encoded rules from YAML, pair with bundled verbatim text.

    Returns one RegulationSection per top-level ``sections`` entry. Each rule's
    Citation is built via ``Citation.from_quote`` from the YAML's ``source_quote``
    plus the section's ``source_url``.

    Raises:
        FileNotFoundError: if either input file is missing.
        ValueError: if the YAML references a section not present in the bundle.
    """
    yaml_path = yaml_path or _DEFAULT_YAML
    bundle_path = bundle_path or _DEFAULT_BUNDLE

    if not yaml_path.exists():
        raise FileNotFoundError(f"encoded YAML not found: {yaml_path}")
    if not bundle_path.exists():
        raise FileNotFoundError(f"bundled CFR text not found: {bundle_path}")

    bundle_text = bundle_path.read_text(encoding="utf-8")
    bundle_by_num = _slice_bundle_by_section(bundle_text)

    raw = cast(dict[str, Any], yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
    meta = raw.get("metadata", {})
    publication_date = meta.get("publication_date")

    sections: list[RegulationSection] = []
    for raw_section in raw.get("sections", []):
        section_id = cast(str, raw_section["id"])
        num = _section_num_from_id(section_id)
        if num not in bundle_by_num:
            raise ValueError(
                f"section {section_id!r} declared in YAML but missing from bundled text"
            )
        full_text = bundle_by_num[num]
        section_source_url = cast(str, raw_section["source_url"])

        rules: list[Rule] = []
        for raw_rule in raw_section.get("rules", []):
            quote = cast(str, raw_rule["source_quote"]).strip()
            citation = Citation.from_quote(
                source_url=section_source_url,
                source_section=section_id,
                source_quote=quote,
                publication_date=publication_date,
            )
            rule = Rule(
                id=raw_rule["id"],
                section_id=section_id,
                text=raw_rule["text"].strip(),
                rule_type=raw_rule["rule_type"],
                triggers=raw_rule.get("triggers", []),
                requires_consent=raw_rule.get("requires_consent", False),
                requires_directory_opt_out_check=raw_rule.get(
                    "requires_directory_opt_out_check", False
                ),
                requires_legitimate_educational_interest=raw_rule.get(
                    "requires_legitimate_educational_interest", False
                ),
                safe_harbor_conditions=raw_rule.get("safe_harbor_conditions", []),
                citation=citation,
                severity=raw_rule.get("severity", "block"),
                rationale=raw_rule["rationale"].strip(),
            )
            rules.append(rule)
            if audit_sink is not None:
                emit_event(
                    EventAction.RULE_ENCODED,
                    payload={"rule_id": rule.id, "section_id": section_id},
                    sink=audit_sink,
                )

        section = RegulationSection(
            id=section_id,
            title=raw_section["title"].strip(),
            subpart=raw_section["subpart"],
            full_text=full_text,
            full_text_hash=sha256_hex(full_text),
            rules=rules,
            source_url=section_source_url,
            retrieved_at=datetime.now(UTC),
        )
        sections.append(section)
        if audit_sink is not None:
            emit_event(
                EventAction.SECTION_LOADED,
                payload={
                    "section_id": section_id,
                    "rule_count": len(rules),
                    "full_text_hash": section.full_text_hash[:16],
                },
                sink=audit_sink,
            )

    return sections


def flatten_rules(sections: list[RegulationSection]) -> list[Rule]:
    """Convenience: flatten ``[Section→[Rule]]`` into a single ``list[Rule]``."""
    return [rule for section in sections for rule in section.rules]
