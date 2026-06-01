"""``regrails coverage`` sub-app — rule-to-scenario traceability matrix."""

from __future__ import annotations

from pathlib import Path

import typer

from ..coverage import build_matrix, to_markdown

app = typer.Typer(help="Rule-to-scenario coverage matrix.", no_args_is_help=True)


@app.command("report")
def report(
    out: Path | None = typer.Option(None, "--out", help="Write the matrix to this Markdown file."),
) -> None:
    """Build the coverage matrix from the golden corpus and print or write it."""
    rows, scenarios, rules = build_matrix()
    md = to_markdown(rows, scenarios, rules)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md + "\n", encoding="utf-8")
        covered = sum(1 for r in rows if r["n_scenarios"] > 0)
        typer.echo(f"Wrote {out}: {covered}/{len(rules)} rules covered by {len(scenarios)} scenarios.")
    else:
        typer.echo(md)
