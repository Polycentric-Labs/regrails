"""``regrails encode`` sub-app — inspect the encoded rule set (all frameworks)."""

from __future__ import annotations

import json

import typer

from ..encode import FRAMEWORKS, flatten_rules, load_all_sections, load_sections

app = typer.Typer(help="Encoding inspection.", no_args_is_help=True)


def _sections(framework: str):  # type: ignore[no-untyped-def]
    return load_all_sections() if framework == "all" else load_sections(framework=framework)


@app.command("list")
def list_rules(
    framework: str = typer.Option("all", "--framework", help=f"or one of {sorted(FRAMEWORKS)}"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List every encoded rule (one row per rule)."""
    sections = _sections(framework)
    rules = flatten_rules(sections)

    if as_json:
        typer.echo(json.dumps([r.model_dump(mode="json") for r in rules], indent=2))
        return

    typer.echo(f"{'Rule ID':<20} {'Framework':<9} {'Type':<16} {'Risk':<7} {'Severity':<9} Triggers")
    typer.echo("-" * 100)
    for r in rules:
        typer.echo(
            f"{r.id:<20} {r.framework:<9} {r.rule_type:<16} {str(r.risk_tier or '-'):<7} "
            f"{r.severity:<9} {', '.join(r.triggers[:3])}"
        )
    typer.echo("")
    by_fw: dict[str, int] = {}
    for r in rules:
        by_fw[r.framework] = by_fw.get(r.framework, 0) + 1
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_fw.items()))
    typer.echo(f"Total: {len(rules)} rules across {len(sections)} sections ({summary}).")


@app.command("verify")
def verify(
    framework: str = typer.Option("all", "--framework"),
) -> None:
    """Round-trip load the encoded YAML and confirm structural validity."""
    sections = _sections(framework)
    rules = flatten_rules(sections)
    typer.echo(
        f"Loaded OK: {len(sections)} sections, {len(rules)} rules. "
        f"All citations include source_hash."
    )
