"""``regrails export`` sub-app — export the encoded rules to interchange formats."""

from __future__ import annotations

from pathlib import Path

import typer

from ..oscal import build_catalog, to_json

app = typer.Typer(help="Export the encoded rules (OSCAL).", no_args_is_help=True)


@app.command("oscal")
def oscal(
    out: Path | None = typer.Option(None, "--out", help="Write the OSCAL catalog JSON here."),
) -> None:
    """Export the encoded rules as an OSCAL 1.1.2-shaped catalog."""
    catalog = build_catalog()
    text = to_json(catalog)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        n = sum(len(g["controls"]) for g in catalog["catalog"]["groups"])
        typer.echo(f"Wrote {out}: OSCAL 1.1.2-shaped catalog, {n} controls.")
    else:
        typer.echo(text)
