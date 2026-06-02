"""Doc link check: every relative Markdown link in the repo must resolve to a file.

A lightweight, dependency-free link checker for the safeguards suite (S3). It scans
``README.md`` plus ``docs/*.md`` for inline Markdown links ``[text](target)`` and
verifies that every *relative* link points at a path that actually exists on disk.
External links (``http://`` / ``https://`` / ``mailto:``) and pure in-page anchors
(``#section``) are intentionally skipped — this gate guards against broken in-repo
references (a renamed/moved doc, a typo'd path), not link rot on the open web.

A ``path#anchor`` target is checked for the file part only (the anchor is ignored).

Usage::

    uv run python scripts/check_docs_links.py            # scan README.md + docs/*.md
    uv run python scripts/check_docs_links.py path/to.md  # scan specific files

Exit code: ``0`` if every relative link resolves; ``1`` (with a per-link report) if
any is broken. Designed to run in CI (``.github/workflows/consistency.yml``).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Inline Markdown links: [text](target). Reference-style links and bare autolinks
# are not used in these docs; keeping the matcher narrow avoids false positives.
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Schemes / forms that are NOT local files and must be skipped.
_SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


def _default_targets() -> list[Path]:
    """README.md + every docs/*.md, the canonical human-facing surface."""
    targets = [_REPO_ROOT / "README.md"]
    docs = _REPO_ROOT / "docs"
    if docs.is_dir():
        targets.extend(sorted(docs.glob("*.md")))
    return [p for p in targets if p.is_file()]


def _extract_targets(markdown: str) -> list[str]:
    return _LINK_RE.findall(markdown)


def _is_local(target: str) -> bool:
    return not target.startswith(_SKIP_PREFIXES)


def check_file(md_path: Path) -> list[str]:
    """Return a list of human-readable error strings for broken relative links."""
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    for raw in _extract_targets(text):
        target = raw.strip()
        if not target or not _is_local(target):
            continue
        # Strip any in-page anchor; resolve the file part relative to the doc.
        file_part = target.split("#", 1)[0]
        if not file_part:  # pure anchor like "(#section)" — handled by _SKIP_PREFIXES, but be safe
            continue
        resolved = (md_path.parent / file_part).resolve()
        if not resolved.exists():
            rel = md_path.relative_to(_REPO_ROOT)
            errors.append(f"{rel}: broken link -> '{target}' (resolved: {resolved})")
    return errors


def main(argv: list[str]) -> int:
    targets = [Path(a).resolve() for a in argv] if argv else _default_targets()

    all_errors: list[str] = []
    for md_path in targets:
        if not md_path.is_file():
            all_errors.append(f"not a file: {md_path}")
            continue
        all_errors.extend(check_file(md_path))

    if all_errors:
        print("Doc link check FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        print(f"\n{len(all_errors)} broken link(s) across {len(targets)} file(s).")
        return 1

    print(f"Doc link check OK: all relative links resolve across {len(targets)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
