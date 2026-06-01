"""``regrails check`` sub-app — faithfulness gate across all frameworks."""

from __future__ import annotations

import typer

from ..encode import FRAMEWORKS, load_all_sections, load_sections
from ..faithfulness import DEFAULT_THRESHOLD, check_sections

app = typer.Typer(help="Faithfulness + validation checks.", no_args_is_help=True)


@app.command("faithfulness")
def faithfulness(
    framework: str = typer.Option(
        "all", "--framework", help=f"Framework to check, or 'all'. Known: {sorted(FRAMEWORKS)}"
    ),
    threshold: float = typer.Option(
        DEFAULT_THRESHOLD, "--threshold", min=0.0, max=1.0,
        help="Token-coverage threshold (a rule passes if its source_quote is verbatim OR "
        "coverage >= threshold).",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print the full per-rule table."),
) -> None:
    """Check every encoded rule's source_quote against the bundled regulatory text."""
    sections = load_all_sections() if framework == "all" else load_sections(framework=framework)
    report = check_sections(sections, threshold=threshold)

    if verbose or not report.passed:
        typer.echo(report.to_markdown_table())
        typer.echo("")

    total = len(report.results)
    scope = "all frameworks" if framework == "all" else framework
    typer.echo(
        f"Faithfulness ({scope}): {report.passed_count}/{total} rules passed "
        f"at threshold {threshold:.2f}"
    )

    if not report.passed:
        typer.echo("\nFailing rules:")
        for r in report.failed:
            typer.echo(
                f"  - {r.rule_id} ({r.section_id}): substring={r.is_substring}, "
                f"coverage={r.coverage:.3f}"
            )
            if r.missing_tokens:
                preview = ", ".join(r.missing_tokens[:8])
                more = "" if len(r.missing_tokens) <= 8 else f" (+{len(r.missing_tokens) - 8} more)"
                typer.echo(f"      tokens not in section: {preview}{more}")
        raise typer.Exit(code=1)
