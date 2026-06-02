"""Release gate: assert RegRails' version agrees across all three declarations.

RegRails states its version in three independent places:

1. ``regrails.__version__`` — the installed package (single source of truth in code),
2. ``[project].version`` in ``pyproject.toml`` — what ``uv build`` / PyPI publish,
3. the ``regrails==X`` pin in ``web/requirements.txt`` — what the web app deploys.

If a release bumps one but forgets another, the website ships pinned to a version
PyPI may not yet have (or the wheel ships under the wrong number). This script
reads all three, prints any disagreement, and exits non-zero so CI / the release
runbook fails closed. It exits 0 only when all three are byte-identical.

Usage::

    uv run python scripts/check_version_consistency.py
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_WEB_REQUIREMENTS = _REPO_ROOT / "web" / "requirements.txt"

# Matches ``regrails==0.3.1`` (optionally with surrounding whitespace / a trailing
# comment), capturing the pinned version. Only the ``==`` exact pin is accepted —
# a release pin must be exact, not ``>=`` / ``~=``.
_WEB_PIN_RE = re.compile(r"^\s*regrails\s*==\s*([^\s#]+)", re.MULTILINE)


def package_version() -> str:
    """Return ``regrails.__version__`` from the installed package."""
    from regrails import __version__

    return __version__


def pyproject_version() -> str:
    """Return ``[project].version`` from ``pyproject.toml`` via ``tomllib``."""
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    version = data["project"]["version"]
    if not isinstance(version, str):  # pragma: no cover - tomllib guarantees str here
        raise TypeError(f"[project].version is not a string: {version!r}")
    return version


def web_requirements_pin() -> str | None:
    """Return the ``regrails==X`` pin from ``web/requirements.txt``, or ``None``.

    ``None`` means no exact ``regrails==`` pin was found at all — itself a problem
    the gate reports (the web app must pin an exact RegRails version).
    """
    if not _WEB_REQUIREMENTS.exists():
        return None
    match = _WEB_PIN_RE.search(_WEB_REQUIREMENTS.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def check() -> list[str]:
    """Compare the three version declarations; return a list of problem strings.

    An empty list means everything agrees (the gate passes). Each entry is a
    human-readable description of one disagreement.
    """
    pkg = package_version()
    proj = pyproject_version()
    web = web_requirements_pin()

    problems: list[str] = []

    if web is None:
        problems.append(
            f"web/requirements.txt has no exact 'regrails==' pin "
            f"(expected 'regrails=={pkg}')."
        )

    if proj != pkg:
        problems.append(
            f"pyproject.toml [project].version ({proj!r}) != "
            f"regrails.__version__ ({pkg!r})."
        )

    if web is not None and web != pkg:
        problems.append(
            f"web/requirements.txt pin (regrails=={web}) != "
            f"regrails.__version__ ({pkg!r})."
        )

    return problems


def main() -> int:
    """Print the result and return a process exit code (0 = consistent)."""
    problems = check()
    pkg = package_version()

    if not problems:
        print(f"Version consistency OK: regrails.__version__, pyproject.toml, and "
              f"web/requirements.txt all agree on {pkg}.")
        return 0

    print(f"Version INCONSISTENCY detected (regrails.__version__ = {pkg}):")
    for problem in problems:
        print(f"  - {problem}")
    print("\nBump all three together before tagging a release.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
