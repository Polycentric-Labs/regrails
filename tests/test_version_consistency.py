"""Tests for the version-consistency release gate (``scripts/check_version_consistency.py``).

The gate asserts three independent declarations of the RegRails version agree:

1. ``regrails.__version__`` (the installed package),
2. ``[project].version`` in ``pyproject.toml`` (what gets built + published),
3. the ``regrails==X`` pin in ``web/requirements.txt`` (what the web app deploys).

A real release that bumps one but forgets another ships a website pinned to a
version PyPI does not yet have — exactly the drift this gate exists to catch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import check_version_consistency as cvc  # noqa: E402


def test_real_repo_is_consistent() -> None:
    """The committed repo must currently agree across all three sources."""
    assert cvc.check() == []


def test_all_three_sources_agree_on_the_same_string() -> None:
    """Sanity: the three readers return identical, non-empty version strings."""
    pkg = cvc.package_version()
    proj = cvc.pyproject_version()
    web = cvc.web_requirements_pin()
    assert pkg == proj == web
    assert pkg  # non-empty


def test_mismatched_pyproject_yields_a_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cvc, "pyproject_version", lambda: "9.9.9")
    problems = cvc.check()
    assert problems  # at least one
    assert any("pyproject.toml" in p for p in problems)


def test_mismatched_web_pin_yields_a_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cvc, "web_requirements_pin", lambda: "0.0.1")
    problems = cvc.check()
    assert problems
    assert any("requirements.txt" in p for p in problems)


def test_mismatched_package_version_yields_a_problem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cvc, "package_version", lambda: "1.2.3")
    problems = cvc.check()
    assert problems
    assert any("__version__" in p for p in problems)


@pytest.mark.parametrize(
    ("pkg", "proj", "web"),
    [
        ("0.3.1", "0.3.2", "0.3.1"),  # pyproject ahead
        ("0.3.1", "0.3.1", "0.3.0"),  # web pin behind
        ("0.4.0", "0.3.1", "0.3.1"),  # package ahead
        ("1.0.0", "2.0.0", "3.0.0"),  # all three differ
    ],
)
def test_any_disagreement_is_caught(
    monkeypatch: pytest.MonkeyPatch, pkg: str, proj: str, web: str
) -> None:
    monkeypatch.setattr(cvc, "package_version", lambda: pkg)
    monkeypatch.setattr(cvc, "pyproject_version", lambda: proj)
    monkeypatch.setattr(cvc, "web_requirements_pin", lambda: web)
    assert cvc.check()  # non-empty -> a mismatch was reported


def test_missing_web_pin_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A requirements.txt with no ``regrails==`` line is itself a problem."""

    def _no_pin() -> str | None:
        return None

    monkeypatch.setattr(cvc, "web_requirements_pin", _no_pin)
    problems = cvc.check()
    assert any("requirements.txt" in p for p in problems)


def test_main_exits_zero_when_consistent() -> None:
    assert cvc.main() == 0


def test_main_exits_nonzero_on_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cvc, "pyproject_version", lambda: "9.9.9")
    assert cvc.main() != 0
