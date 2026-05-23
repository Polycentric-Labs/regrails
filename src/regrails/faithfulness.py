"""Verbatim-text faithfulness gate.

Direct port of the Jaccard-on-tokens algorithm from Evidentia's
`evidentia_ai.eval.faithfulness` (``_tokenize`` + ``_jaccard``, lines 91 +
242-265 of that file).

For every Rule in the encoded YAML, we check two things against the bundled
CFR text:

1. **Substring containment** — does ``rule.citation.source_quote`` appear
   character-for-character inside the matching section's ``full_text``?
2. **Token Jaccard** — between the tokenized source_quote and the tokenized
   section full_text. The bundle is large; Jaccard against the entire section
   will be low. The check we actually care about is "are *all* of the quote's
   tokens present in the section?" — formally ``|quote ∩ full_text| /
   |quote| >= 0.85`` (a one-sided coverage variant of Jaccard).

A rule **passes** iff substring containment OR coverage ≥ 0.85. We track
both so the report shows which check carried the rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .models import RegulationSection, Rule

DEFAULT_THRESHOLD = 0.85
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Extract a lowercase token set from ``text`` (ASCII alphanumeric only).

    Ported verbatim from Evidentia's ``_tokenize`` (line 242).
    """
    return {match.group(0).lower() for match in _TOKEN_RE.finditer(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity ``|A ∩ B| / |A ∪ B|``.

    Ported verbatim from Evidentia's ``_jaccard`` (line 254). Returns 0.0 if
    both sets are empty (matches the "no overlap" semantics operators expect).
    """
    if not a and not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def _coverage(quote: set[str], full: set[str]) -> float:
    """One-sided coverage: ``|quote ∩ full| / |quote|``.

    This is the metric operators actually want for "the quoted span is verbatim
    from the source": every token in the quote should appear somewhere in the
    source. Returns 0.0 for an empty quote.
    """
    if not quote:
        return 0.0
    return len(quote & full) / len(quote)


@dataclass(frozen=True)
class RuleFaithfulness:
    rule_id: str
    section_id: str
    is_substring: bool
    jaccard: float
    coverage: float
    passed: bool
    missing_tokens: tuple[str, ...]  # tokens in quote but NOT in section full_text


@dataclass(frozen=True)
class FaithfulnessReport:
    threshold: float
    results: tuple[RuleFaithfulness, ...]

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> tuple[RuleFaithfulness, ...]:
        return tuple(r for r in self.results if not r.passed)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    def to_markdown_table(self) -> str:
        """Render a markdown table for CLI / CI logs."""
        lines = [
            "| Rule | Section | substring? | Jaccard | Coverage | Passed |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.results:
            lines.append(
                f"| `{r.rule_id}` | `{r.section_id}` | "
                f"{'✅' if r.is_substring else '—'} | "
                f"{r.jaccard:.3f} | {r.coverage:.3f} | "
                f"{'✅' if r.passed else '❌'} |"
            )
        return "\n".join(lines)


def check_rule(
    rule: Rule,
    section: RegulationSection,
    threshold: float = DEFAULT_THRESHOLD,
) -> RuleFaithfulness:
    quote = rule.citation.source_quote
    quote_tokens = _tokenize(quote)
    full_tokens = _tokenize(section.full_text)

    is_substring = quote in section.full_text
    jaccard = _jaccard(quote_tokens, full_tokens)
    coverage = _coverage(quote_tokens, full_tokens)
    passed = is_substring or coverage >= threshold
    missing = tuple(sorted(quote_tokens - full_tokens))

    return RuleFaithfulness(
        rule_id=rule.id,
        section_id=section.id,
        is_substring=is_substring,
        jaccard=jaccard,
        coverage=coverage,
        passed=passed,
        missing_tokens=missing,
    )


def check_sections(
    sections: list[RegulationSection],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> FaithfulnessReport:
    """Check every rule in every section, return a FaithfulnessReport."""
    by_id = {s.id: s for s in sections}
    results: list[RuleFaithfulness] = []
    for section in sections:
        for rule in section.rules:
            owner = by_id.get(rule.section_id, section)
            results.append(check_rule(rule, owner, threshold))
    return FaithfulnessReport(threshold=threshold, results=tuple(results))


def check_bundled(
    *,
    yaml_path: Path | None = None,
    bundle_path: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> FaithfulnessReport:
    """Convenience: load_sections() + check_sections()."""
    from .encode import load_sections

    sections = load_sections(yaml_path=yaml_path, bundle_path=bundle_path)
    return check_sections(sections, threshold=threshold)
