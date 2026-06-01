"""Load encoded YAML rules + bundled regulatory text into RegulationSection objects.

v0.2: multi-framework. The bundled POC ships two frameworks — FERPA (34 CFR
Part 99 Subpart D) and a Title IV subset (34 CFR Part 668) — each a (yaml, bundle)
pair in ``FRAMEWORKS``. ``load_sections()`` defaults to FERPA for backward
compatibility; ``load_all_sections()`` / ``load_all_rules()`` span every framework.
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
_DATA = _PROJECT_ROOT / "data"

# Framework registry: name -> (encoded YAML, bundled verbatim text).
FRAMEWORKS: dict[str, tuple[Path, Path]] = {
    "FERPA": (
        _DATA / "encoded" / "ferpa-subpart-d.yaml",
        _DATA / "cfr" / "ferpa-subpart-d.txt",
    ),
    "Title IV": (
        _DATA / "encoded" / "title-iv-subset.yaml",
        _DATA / "cfr" / "title-iv-subset.txt",
    ),
}


def default_paths() -> tuple[Path, Path]:
    """Return the FERPA (yaml_path, bundle_path) — kept for backward compatibility."""
    return FRAMEWORKS["FERPA"]


def framework_paths(framework: str) -> tuple[Path, Path]:
    """Return the (yaml_path, bundle_path) for a registered framework."""
    if framework not in FRAMEWORKS:
        raise ValueError(f"unknown framework: {framework!r}; known: {sorted(FRAMEWORKS)}")
    return FRAMEWORKS[framework]


def _slice_bundle_by_section(bundle_text: str) -> dict[str, str]:
    """Split bundled text into ``{ "99.31": "<full chunk incl. heading>", ... }``."""
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
        out[heading_match.group("num")] = chunk
    return out


def _section_num_from_id(section_id: str) -> str:
    """Extract ``99.31`` from ``34-CFR-99.31`` (or ``668.34`` from ``34-CFR-668.34``)."""
    m = re.match(r"^\d+-CFR-(?P<num>\d+(?:\.\d+)*)$", section_id)
    if not m:
        raise ValueError(f"unrecognized section id: {section_id!r}")
    return m.group("num")


def load_sections(
    yaml_path: Path | None = None,
    bundle_path: Path | None = None,
    *,
    framework: str = "FERPA",
    audit_sink: Path | None = None,
) -> list[RegulationSection]:
    """Load encoded rules from YAML, pair with bundled verbatim text.

    If ``yaml_path``/``bundle_path`` are given they win; otherwise the paths are
    looked up from ``FRAMEWORKS[framework]``. The framework label is taken from the
    YAML ``metadata.framework`` when present, else the ``framework`` argument.
    """
    if yaml_path is None or bundle_path is None:
        fw_yaml, fw_bundle = framework_paths(framework)
        yaml_path = yaml_path or fw_yaml
        bundle_path = bundle_path or fw_bundle

    if not yaml_path.exists():
        raise FileNotFoundError(f"encoded YAML not found: {yaml_path}")
    if not bundle_path.exists():
        raise FileNotFoundError(f"bundled text not found: {bundle_path}")

    bundle_text = bundle_path.read_text(encoding="utf-8")
    bundle_by_num = _slice_bundle_by_section(bundle_text)

    raw = cast(dict[str, Any], yaml.safe_load(yaml_path.read_text(encoding="utf-8")))
    meta = raw.get("metadata", {})
    publication_date = meta.get("publication_date")
    fw_label = meta.get("framework", framework)

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
                framework=fw_label,
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
                risk_tier=raw_rule.get("risk_tier"),
                citation=citation,
                severity=raw_rule.get("severity", "block"),
                rationale=raw_rule["rationale"].strip(),
            )
            rules.append(rule)
            if audit_sink is not None:
                emit_event(
                    EventAction.RULE_ENCODED,
                    payload={"rule_id": rule.id, "section_id": section_id, "framework": fw_label},
                    sink=audit_sink,
                )

        section = RegulationSection(
            id=section_id,
            framework=fw_label,
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
                    "framework": fw_label,
                    "rule_count": len(rules),
                    "full_text_hash": section.full_text_hash[:16],
                },
                sink=audit_sink,
            )

    return sections


def load_all_sections(*, audit_sink: Path | None = None) -> list[RegulationSection]:
    """Load every registered framework's sections, concatenated."""
    out: list[RegulationSection] = []
    for name in FRAMEWORKS:
        out.extend(load_sections(framework=name, audit_sink=audit_sink))
    return out


def flatten_rules(sections: list[RegulationSection]) -> list[Rule]:
    """Flatten ``[Section -> [Rule]]`` into a single ``list[Rule]``."""
    return [rule for section in sections for rule in section.rules]


def load_all_rules() -> list[Rule]:
    """Convenience: every rule across every framework."""
    return flatten_rules(load_all_sections())
