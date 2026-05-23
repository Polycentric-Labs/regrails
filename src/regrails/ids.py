"""CFR identifier normalization and rule-ID slugification.

Borrows the Evidentia `_normalize_control_id` pattern from
`packages/evidentia-core/src/evidentia_core/models/catalog.py`, adapted for
US Code of Federal Regulations citations (e.g., `34 CFR 99.31(a)(1)(i)(B)`).
"""

from __future__ import annotations

import hashlib
import re

_CFR_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "34 CFR 99.31"  /  "34 C.F.R. 99.31"  /  "34 CFR § 99.31"  /  "34cfr99.31"
    re.compile(
        r"^\s*(?P<title>\d{1,3})\s*c\.?\s*f\.?\s*r\.?\s*§?\s*(?P<rest>[\d.\-()A-Za-z\s]+?)\s*$",
        re.IGNORECASE,
    ),
    # "34-CFR-99.31"  /  "34_CFR_99.31"
    re.compile(
        r"^\s*(?P<title>\d{1,3})[-_]cfr[-_](?P<rest>[\d.\-()A-Za-z\s]+?)\s*$",
        re.IGNORECASE,
    ),
)


def normalize_cfr_id(raw: str) -> str:
    """Normalize a CFR citation to canonical form ``<title>-CFR-<rest>``.

    Examples
    --------
    >>> normalize_cfr_id("34 CFR 99.31")
    '34-CFR-99.31'
    >>> normalize_cfr_id("34 C.F.R. § 99.31(a)(1)(i)(B)")
    '34-CFR-99.31.A.1.I.B'
    >>> normalize_cfr_id("34-cfr-99.37")
    '34-CFR-99.37'
    """
    if not raw or not raw.strip():
        raise ValueError("CFR id cannot be empty")
    for pattern in _CFR_PATTERNS:
        match = pattern.match(raw)
        if match:
            title = match.group("title")
            rest = match.group("rest")
            normalized_rest = _normalize_cfr_subscript(rest)
            return f"{title}-CFR-{normalized_rest}"
    raise ValueError(f"Could not parse CFR citation: {raw!r}")


def _normalize_cfr_subscript(text: str) -> str:
    """Turn ``99.31(a)(1)(i)(B)`` into ``99.31.A.1.I.B``.

    Whitespace is stripped; parenthesized groups become dot-segments and are
    upper-cased. Numeric segments are left alone. Empty parens are rejected.
    """
    text = text.strip()
    parts: list[str] = []
    paren_groups: list[str] = []

    # Split base section from parenthesized prongs.
    paren_match = re.search(r"\(", text)
    if paren_match:
        base = text[: paren_match.start()].strip()
        paren_text = text[paren_match.start() :]
        paren_groups = re.findall(r"\(([^()]+)\)", paren_text)
        if "(" in paren_text and not paren_groups:
            raise ValueError(f"Malformed parens in CFR citation segment: {text!r}")
    else:
        base = text

    base = base.replace(" ", "")
    if not base:
        raise ValueError(f"Empty CFR base section: {text!r}")
    parts.append(base)
    parts.extend(_canon_segment(g) for g in paren_groups)
    return ".".join(parts)


def _canon_segment(segment: str) -> str:
    seg = segment.strip()
    if not seg:
        raise ValueError("Empty CFR parenthesized segment")
    return seg.upper()


_RULE_ID_SAFE = re.compile(r"[^A-Z0-9.\-]")


def slugify_rule_id(framework: str, section: str, ordinal: int | str) -> str:
    """Build a stable rule id like ``FERPA-99.31-A1``.

    Parameters
    ----------
    framework:
        Short framework tag, e.g. ``"FERPA"`` (will be upper-cased).
    section:
        CFR section, e.g. ``"34-CFR-99.31"`` or ``"99.31"``. The title and
        ``CFR-`` prefix are stripped if present, leaving only the section
        identifier.
    ordinal:
        A short suffix distinguishing rules within the section. Letters are
        upper-cased; integers are left as-is.
    """
    framework_part = framework.strip().upper()
    if not framework_part:
        raise ValueError("framework cannot be empty")
    section_part = section.strip().upper().removeprefix("34-CFR-")
    section_part = re.sub(r"^[0-9]+-CFR-", "", section_part)
    if not section_part:
        raise ValueError(f"Could not extract section from {section!r}")
    ordinal_part = str(ordinal).strip().upper()
    if not ordinal_part:
        raise ValueError("ordinal cannot be empty")
    slug = f"{framework_part}-{section_part}-{ordinal_part}"
    if _RULE_ID_SAFE.search(slug):
        raise ValueError(f"slug contains disallowed characters: {slug!r}")
    return slug


def sha256_hex(text: str) -> str:
    """Return the lower-case hex SHA-256 of ``text`` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
