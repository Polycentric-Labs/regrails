"""``regrails check`` sub-app — faithfulness gate + smoke commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ..encode import default_paths
from ..faithfulness import DEFAULT_THRESHOLD, check_bundled

app = typer.Typer(help="Faithfulness + validation checks.", no_args_is_help=True)


@app.command("faithfulness")
def faithfulness(
    yaml_path: Path | None = typer.Option(
        None, "--yaml", help="Encoded YAML path (defaults to bundled FERPA Subpart D)."
    ),
    bundle_path: Path | None = typer.Option(
        None, "--bundle", help="Bundled CFR text path (defaults to bundled FERPA Subpart D)."
    ),
    threshold: float = typer.Option(
        DEFAULT_THRESHOLD,
        "--threshold",
        min=0.0,
        max=1.0,
        help="Token-coverage threshold (a rule passes if its source_quote is found "
        "verbatim OR its coverage >= threshold).",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print the full per-rule table."),
) -> None:
    """Check every encoded rule's source_quote against the bundled CFR text."""
    yp, bp = default_paths()
    report = check_bundled(
        yaml_path=yaml_path or yp,
        bundle_path=bundle_path or bp,
        threshold=threshold,
    )

    if verbose or not report.passed:
        typer.echo(report.to_markdown_table())
        typer.echo("")

    total = len(report.results)
    typer.echo(
        f"Faithfulness: {report.passed_count}/{total} rules passed at threshold {threshold:.2f}"
    )

    if not report.passed:
        typer.echo("")
        typer.echo("Failing rules:")
        for r in report.failed:
            typer.echo(
                f"  - {r.rule_id} ({r.section_id}): "
                f"substring={r.is_substring}, coverage={r.coverage:.3f}"
            )
            if r.missing_tokens:
                preview = ", ".join(r.missing_tokens[:8])
                more = "" if len(r.missing_tokens) <= 8 else f" (+{len(r.missing_tokens) - 8} more)"
                typer.echo(f"      tokens not in section: {preview}{more}")
        raise typer.Exit(code=1)
