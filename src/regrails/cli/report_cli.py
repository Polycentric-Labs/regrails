"""``regrails report`` sub-app — render recorded decisions to a static HTML report."""

from __future__ import annotations

from pathlib import Path

import typer

from ..report import build_report

app = typer.Typer(help="Static HTML decision report.", no_args_is_help=True)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_RECORDED = _PROJECT_ROOT / "demo" / "recorded-runs"
_CHAIN = _RECORDED / "decisions.chain.jsonl"


@app.command("html")
def html_report(
    recorded_dir: Path = typer.Option(_RECORDED, "--recorded-dir"),
    chain: Path = typer.Option(_CHAIN, "--chain"),
    out: Path = typer.Option(
        _PROJECT_ROOT / "docs" / "decision-report.html", "--out"
    ),
) -> None:
    """Build a self-contained HTML report from demo/recorded-runs."""
    html = build_report(recorded_dir, chain)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    typer.echo(f"Wrote {out} ({len(html)} bytes).")
