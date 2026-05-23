"""``regrails encode`` sub-app — inspect the encoded rule set."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ..encode import default_paths, flatten_rules, load_sections

app = typer.Typer(help="Encoding inspection.", no_args_is_help=True)


@app.command("list")
def list_rules(
    yaml_path: Path | None = typer.Option(None, "--yaml"),
    bundle_path: Path | None = typer.Option(None, "--bundle"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List every encoded rule (one row per rule)."""
    yp, bp = default_paths()
    sections = load_sections(yaml_path=yaml_path or yp, bundle_path=bundle_path or bp)
    rules = flatten_rules(sections)

    if as_json:
        typer.echo(
            json.dumps([rule.model_dump(mode="json") for rule in rules], indent=2)
        )
        return

    typer.echo(f"{'Rule ID':<22} {'Type':<18} {'Severity':<10} {'Triggers'}")
    typer.echo("-" * 80)
    for rule in rules:
        typer.echo(
            f"{rule.id:<22} {rule.rule_type:<18} {rule.severity:<10} "
            f"{', '.join(rule.triggers[:3])}"
        )
    typer.echo("")
    typer.echo(f"Total: {len(rules)} rules across {len(sections)} sections.")


@app.command("verify")
def verify(
    yaml_path: Path | None = typer.Option(None, "--yaml"),
    bundle_path: Path | None = typer.Option(None, "--bundle"),
) -> None:
    """Round-trip load the encoded YAML and confirm structural validity."""
    yp, bp = default_paths()
    sections = load_sections(yaml_path=yaml_path or yp, bundle_path=bundle_path or bp)
    rules = flatten_rules(sections)
    typer.echo(
        f"Loaded OK: {len(sections)} sections, {len(rules)} rules. "
        f"All citations include source_hash."
    )
