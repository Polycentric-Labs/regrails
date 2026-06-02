"""Tests for the CLI<->web parity gate (``scripts/check_parity.py``).

The gate keeps ``docs/cli-web-parity.yaml`` honest against the live Typer tree and
the web route registry:

* COMPLETENESS  - every live CLI leaf is triaged in the manifest (HARD failure).
* REGISTRY      - every ``web`` route the manifest claims exists in
                  ``web/src/routes/registry.tsx`` (HARD failure).
* DEBT-RATCHET  - the ``cli-only`` count can't exceed the committed baseline
                  (advisory by default; HARD under ``--strict``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import check_parity as cp  # noqa: E402


# --------------------------------------------------------------------------- #
# live tree + manifest fixtures
# --------------------------------------------------------------------------- #
def test_live_leaves_are_the_expected_twelve() -> None:
    """Pin the real Typer leaf set so a CLI change is a conscious test edit."""
    leaves = set(cp.live_cli_leaves())
    assert leaves == {
        "decide",
        "check faithfulness",
        "encode list",
        "encode verify",
        "research run",
        "audit verify",
        "coverage report",
        "report html",
        "mcp serve",
        "export oscal",
        "bench run",
        "bench report",
    }


def test_leaves_include_top_level_decide() -> None:
    assert "decide" in cp.live_cli_leaves()


def test_manifest_loads_and_has_rows() -> None:
    rows = cp.manifest_commands(cp.load_manifest())
    assert rows
    assert all("cli" in r and "status" in r for r in rows)


def test_every_status_is_a_known_value() -> None:
    rows = cp.manifest_commands(cp.load_manifest())
    assert all(r["status"] in cp.VALID_STATUSES for r in rows)


# --------------------------------------------------------------------------- #
# completeness (hard)
# --------------------------------------------------------------------------- #
def test_completeness_passes_on_the_real_repo() -> None:
    assert cp.check_completeness() == []


def test_planted_unlisted_command_fails_completeness(monkeypatch: pytest.MonkeyPatch) -> None:
    """The headline guarantee: a NEW leaf absent from the manifest fails the gate."""
    leaves = [*cp.live_cli_leaves(), "newgroup shinycmd"]
    monkeypatch.setattr(cp, "live_cli_leaves", lambda: leaves)
    problems = cp.check_completeness()
    assert problems
    assert any("newgroup shinycmd" in p for p in problems)


def test_completeness_ignores_extra_manifest_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest that lists MORE than the live tree still passes completeness
    (completeness == every live leaf is listed, not the converse)."""
    only_a_few = ["decide", "coverage report"]
    monkeypatch.setattr(cp, "live_cli_leaves", lambda: only_a_few)
    assert cp.check_completeness() == []


# --------------------------------------------------------------------------- #
# registry presence (hard)
# --------------------------------------------------------------------------- #
def test_registry_routes_parsed_from_tsx() -> None:
    routes = cp.registry_routes()
    # The known SPA destinations must all parse out of registry.tsx.
    for path in ("/", "/rules", "/coverage", "/benchmark", "/provenance", "/exports", "/mcp"):
        assert path in routes


def test_registry_check_passes_on_the_real_repo() -> None:
    assert cp.check_registry() == []


def test_manifest_route_absent_from_registry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"cli": "decide", "web": "/ghost-route", "status": "full", "reason": "x"}]
    monkeypatch.setattr(cp, "manifest_commands", lambda _m=None: rows)
    problems = cp.check_registry()
    assert problems
    assert any("/ghost-route" in p for p in problems)


def test_null_web_rows_are_not_registry_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"cli": "mcp serve", "web": None, "status": "exempt", "reason": "x"}]
    monkeypatch.setattr(cp, "manifest_commands", lambda _m=None: rows)
    assert cp.check_registry() == []


# --------------------------------------------------------------------------- #
# debt ratchet (advisory by default, hard under --strict)
# --------------------------------------------------------------------------- #
def test_ratchet_passes_at_or_below_baseline() -> None:
    assert cp.check_ratchet() == []


def test_ratchet_flags_when_cli_only_exceeds_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        {"cli": "a a", "web": None, "status": "cli-only", "reason": "x"},
        {"cli": "b b", "web": None, "status": "cli-only", "reason": "x"},
        {"cli": "c c", "web": None, "status": "cli-only", "reason": "x"},
    ]
    monkeypatch.setattr(cp, "manifest_commands", lambda _m=None: rows)
    monkeypatch.setattr(cp, "cli_only_baseline", lambda _m=None: 1)
    problems = cp.check_ratchet()
    assert problems
    assert any("cli-only" in p for p in problems)


def test_baseline_comes_from_the_manifest() -> None:
    assert isinstance(cp.cli_only_baseline(), int)
    assert cp.cli_only_baseline() >= 0


# --------------------------------------------------------------------------- #
# summary + status counts
# --------------------------------------------------------------------------- #
def test_summarize_counts_each_status() -> None:
    s = cp.summarize()
    assert s.full + s.web_only + s.cli_only + s.exempt == s.total
    assert s.total == len(cp.manifest_commands(cp.load_manifest()))
    # the real manifest has at least one of each of these
    assert s.full >= 1
    assert s.exempt >= 1
    assert s.cli_only >= 1


# --------------------------------------------------------------------------- #
# run() / main() exit semantics
# --------------------------------------------------------------------------- #
def test_run_default_exits_zero_on_real_repo() -> None:
    assert cp.run(strict=False) == 0


def test_run_strict_exits_zero_on_real_repo() -> None:
    """The committed repo is clean even under --strict (ratchet at baseline)."""
    assert cp.run(strict=True) == 0


def test_run_fails_when_completeness_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    leaves = [*cp.live_cli_leaves(), "newgroup shinycmd"]
    monkeypatch.setattr(cp, "live_cli_leaves", lambda: leaves)
    # completeness is HARD even in non-strict (default) mode
    assert cp.run(strict=False) != 0


def test_run_fails_when_registry_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"cli": "decide", "web": "/ghost-route", "status": "full", "reason": "x"}]
    monkeypatch.setattr(cp, "manifest_commands", lambda _m=None: rows)
    assert cp.run(strict=False) != 0


def test_ratchet_is_advisory_in_default_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ratchet breach WARNS but does not fail in default mode ...

    The hard checks are stubbed clean so this isolates the ratchet's effect on the
    exit code: only the ratchet differs between this test and the strict twin.
    """
    monkeypatch.setattr(cp, "check_completeness", list)
    monkeypatch.setattr(cp, "check_registry", list)
    monkeypatch.setattr(cp, "check_ratchet", lambda: ["cli-only over baseline"])
    assert cp.run(strict=False) == 0


def test_ratchet_is_hard_under_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    """... but the SAME breach fails under --strict."""
    monkeypatch.setattr(cp, "check_completeness", list)
    monkeypatch.setattr(cp, "check_registry", list)
    monkeypatch.setattr(cp, "check_ratchet", lambda: ["cli-only over baseline"])
    assert cp.run(strict=True) != 0


def test_main_accepts_strict_flag() -> None:
    assert cp.main([]) == 0
    assert cp.main(["--strict"]) == 0
