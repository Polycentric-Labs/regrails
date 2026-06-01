"""Export the encoded rules as an OSCAL 1.1.2-SHAPED catalog.

OSCAL (Open Security Controls Assessment Language) is the NIST standard the
federal government uses for 800-53 and FedRAMP. This emits the 37 encoded rules
as an OSCAL ``catalog``: one ``group`` per framework, one ``control`` per rule
(with the verbatim-CFR reference link and risk tier), and a ``back-matter`` that
binds each section's SHA-256 — so regulations-as-code is consumable by any OSCAL tool.

HONESTY: this produces a structurally-correct OSCAL catalog (shape asserted in
tests). It is NOT run through the official NIST OSCAL validator here, so the
claim is capped at "OSCAL 1.1.2-shaped," not "validated OSCAL."
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from . import __version__
from .encode import load_all_sections
from .models import RegulationSection, Rule

# Fixed namespace -> deterministic UUIDs (a re-export of the same rules is stable).
_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "regrails.polycentric-labs")


def _slug(rule_id: str) -> str:
    return rule_id.lower()


def _control(rule: Rule) -> dict[str, Any]:
    props: list[dict[str, str]] = [
        {"name": "rule-type", "value": rule.rule_type},
        {"name": "severity", "value": rule.severity},
        {"name": "framework", "value": rule.framework},
    ]
    if rule.risk_tier:
        props.append({"name": "risk-tier", "value": rule.risk_tier})
    return {
        "id": _slug(rule.id),
        "title": rule.text,
        "props": props,
        "links": [{"href": rule.citation.source_url, "rel": "reference"}],
        "parts": [
            {"id": f"{_slug(rule.id)}-stmt", "name": "statement", "prose": rule.rationale}
        ],
    }


def build_catalog(sections: list[RegulationSection] | None = None) -> dict[str, Any]:
    """Build an OSCAL 1.1.2-shaped catalog from the encoded sections."""
    sections = sections if sections is not None else load_all_sections()

    groups: list[dict[str, Any]] = []
    by_fw: dict[str, list[Rule]] = {}
    fw_order: list[str] = []
    for s in sections:
        if s.framework not in by_fw:
            by_fw[s.framework] = []
            fw_order.append(s.framework)
        by_fw[s.framework].extend(s.rules)
    for fw in fw_order:
        groups.append(
            {
                "id": fw.lower().replace(" ", "-"),
                "title": fw,
                "controls": [_control(r) for r in by_fw[fw]],
            }
        )

    resources: list[dict[str, Any]] = [
        {
            "uuid": str(uuid.uuid5(_NS, s.id)),
            "title": s.id,
            "rlinks": [
                {
                    "href": s.source_url,
                    "hashes": [{"algorithm": "SHA-256", "value": s.full_text_hash}],
                }
            ],
        }
        for s in sections
    ]

    return {
        "catalog": {
            "uuid": str(uuid.uuid5(_NS, "regrails-catalog")),
            "metadata": {
                "title": "RegRails encoded rules (FERPA + Title IV subset)",
                "last-modified": datetime.now(UTC).isoformat(),
                "version": __version__,
                "oscal-version": "1.1.2",
            },
            "groups": groups,
            "back-matter": {"resources": resources},
        }
    }


def to_json(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, indent=2)
