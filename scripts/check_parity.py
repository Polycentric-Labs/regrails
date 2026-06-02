"""Release gate: keep the CLI<->web parity manifest honest.

``docs/cli-web-parity.yaml`` declares, one row per live CLI leaf, whether that
capability is reachable on the web (``full`` / ``web-only`` / ``cli-only`` /
``exempt``). This gate enforces three invariants against the LIVE Typer tree and
the web route registry:

1. COMPLETENESS - every live ``regrails`` leaf command appears in the manifest, so
   a newly-added command cannot ship without a parity decision. (HARD failure.)
2. REGISTRY     - every non-null ``web`` route the manifest claims is present in
   ``web/src/routes/registry.tsx``, so a row cannot reference a page that was
   never wired. (HARD failure.)
3. DEBT-RATCHET - the number of ``cli-only`` rows may not exceed the committed
   ``cli_only_baseline``; parity debt can shrink but never grow. (Advisory by
   default; HARD under ``--strict``.)

Default behaviour prints a summary and exits 0 unless a HARD check fails. Pass
``--strict`` to also fail on the debt ratchet (and any advisory warning).

Usage::

    uv run python scripts/check_parity.py            # advisory ratchet
    uv run python scripts/check_parity.py --strict   # ratchet is a hard gate
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST = _REPO_ROOT / "docs" / "cli-web-parity.yaml"
_REGISTRY = _REPO_ROOT / "web" / "src" / "routes" / "registry.tsx"

VALID_STATUSES = frozenset({"full", "web-only", "cli-only", "exempt"})

# Matches ``path: "/rules"`` (single or double quotes) in registry.tsx.
_ROUTE_RE = re.compile(r"""path\s*:\s*['"]([^'"]+)['"]""")


# --------------------------------------------------------------------------- #
# live Typer tree
# --------------------------------------------------------------------------- #
def live_cli_leaves() -> list[str]:
    """Walk the live ``regrails`` Typer app and return every leaf command.

    A leaf is ``"<group> <cmd>"`` for grouped commands (e.g. ``"coverage report"``)
    or the bare command name for top-level commands (e.g. ``"decide"``). The walk
    recurses through nested groups, so the manifest stays correct if the CLI grows
    sub-sub-commands later.
    """
    import typer

    from regrails.cli.main import app

    leaves: list[str] = []

    def _command_name(cmd: typer.models.CommandInfo) -> str:
        if cmd.name:
            return cmd.name
        if cmd.callback is not None:
            return cmd.callback.__name__.replace("_", "-")
        return "<anonymous>"  # pragma: no cover - Typer always names commands

    def _walk(t: typer.Typer, prefix: str) -> None:
        for cmd in t.registered_commands:
            name = _command_name(cmd)
            leaves.append(f"{prefix}{name}".strip())
        for group in t.registered_groups:
            assert group.typer_instance is not None
            group_prefix = f"{prefix}{group.name} "
            _walk(group.typer_instance, group_prefix)

    _walk(app, "")
    return sorted(leaves)


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def load_manifest() -> dict[str, Any]:
    """Parse ``docs/cli-web-parity.yaml`` into a dict."""
    data = yaml.safe_load(_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict):  # pragma: no cover - manifest is always a mapping
        raise TypeError(f"{_MANIFEST} did not parse to a mapping: {type(data)!r}")
    return data


def manifest_commands(manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the list of command rows from the manifest."""
    m = manifest if manifest is not None else load_manifest()
    rows = m.get("commands", [])
    if not isinstance(rows, list):  # pragma: no cover - schema-guarded
        raise TypeError("manifest 'commands' is not a list")
    return [r for r in rows if isinstance(r, dict)]


def cli_only_baseline(manifest: dict[str, Any] | None = None) -> int:
    """Return the committed ``cli_only_baseline`` integer from the manifest."""
    m = manifest if manifest is not None else load_manifest()
    value = m.get("cli_only_baseline", 0)
    if not isinstance(value, int):  # pragma: no cover - schema-guarded
        raise TypeError(f"cli_only_baseline must be an int, got {value!r}")
    return value


# --------------------------------------------------------------------------- #
# web route registry
# --------------------------------------------------------------------------- #
def registry_routes() -> set[str]:
    """Parse the SPA route paths out of ``web/src/routes/registry.tsx``."""
    if not _REGISTRY.exists():  # pragma: no cover - registry always present
        return set()
    return set(_ROUTE_RE.findall(_REGISTRY.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# the three checks
# --------------------------------------------------------------------------- #
def check_completeness() -> list[str]:
    """HARD: every live CLI leaf must be listed in the manifest."""
    listed = {str(r.get("cli", "")).strip() for r in manifest_commands()}
    problems: list[str] = []
    for leaf in live_cli_leaves():
        if leaf not in listed:
            problems.append(
                f"CLI leaf '{leaf}' is not in docs/cli-web-parity.yaml "
                f"(add a row with a status + reason)."
            )
    return problems


def check_registry() -> list[str]:
    """HARD: every non-null ``web`` route must exist in registry.tsx."""
    routes = registry_routes()
    problems: list[str] = []
    for row in manifest_commands():
        web = row.get("web")
        if web in (None, "", "null"):
            continue
        if web not in routes:
            problems.append(
                f"manifest row '{row.get('cli')}' maps to web route '{web}', "
                f"which is not in web/src/routes/registry.tsx."
            )
    return problems


def check_ratchet() -> list[str]:
    """RATCHET: ``cli-only`` count must not exceed the committed baseline."""
    rows = manifest_commands()
    count = sum(1 for r in rows if r.get("status") == "cli-only")
    baseline = cli_only_baseline()
    if count > baseline:
        return [
            f"cli-only count ({count}) exceeds the committed baseline ({baseline}). "
            f"Either bridge a CLI-only command to the web, or (only if truly "
            f"intended) raise cli_only_baseline in docs/cli-web-parity.yaml."
        ]
    return []


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Summary:
    """Per-status counts across the manifest."""

    full: int
    web_only: int
    cli_only: int
    exempt: int

    @property
    def total(self) -> int:
        return self.full + self.web_only + self.cli_only + self.exempt


def summarize() -> Summary:
    """Tally the manifest rows by status."""
    rows = manifest_commands()
    counts: dict[str, int] = dict.fromkeys(VALID_STATUSES, 0)
    for row in rows:
        status = str(row.get("status", ""))
        if status in counts:
            counts[status] += 1
    return Summary(
        full=counts["full"],
        web_only=counts["web-only"],
        cli_only=counts["cli-only"],
        exempt=counts["exempt"],
    )


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def run(strict: bool = False) -> int:
    """Run all checks, print a report, and return an exit code.

    HARD checks (completeness, registry) fail the gate in any mode. The debt
    ratchet is advisory by default and a hard failure under ``strict``.
    """
    summary = summarize()
    hard: list[str] = check_completeness() + check_registry()
    ratchet: list[str] = check_ratchet()

    print(
        "CLI<->web parity: "
        f"{summary.total} commands "
        f"({summary.full} full, {summary.web_only} web-only, "
        f"{summary.cli_only} cli-only, {summary.exempt} exempt)."
    )

    if hard:
        print("\nFAIL - hard parity problems:")
        for problem in hard:
            print(f"  - {problem}")

    if ratchet:
        label = "FAIL" if strict else "WARN"
        print(f"\n{label} - debt ratchet:")
        for problem in ratchet:
            print(f"  - {problem}")

    failed = bool(hard) or (strict and bool(ratchet))
    if not failed:
        suffix = " (strict)" if strict else ""
        print(f"\nParity OK{suffix}.")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat the debt ratchet (and any advisory warning) as a hard failure.",
    )
    args = parser.parse_args(argv)
    return run(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
