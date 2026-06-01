"""``regrails audit`` sub-app — verify the hash-chained decision provenance log."""

from __future__ import annotations

from pathlib import Path

import typer

from ..audit import verify_chain

app = typer.Typer(help="Decision-provenance verification.", no_args_is_help=True)


@app.command("verify")
def verify(
    path: Path = typer.Argument(..., help="Path to a hash-chained decisions JSONL log."),
) -> None:
    """Verify the integrity of a hash-chained decision log (tamper-evidence)."""
    ok, problems = verify_chain(path)
    if ok:
        n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        typer.echo(f"OK: hash chain intact ({n} decision records, no tampering detected).")
        return
    typer.echo("FAILED: hash chain integrity problems detected:")
    for p in problems:
        typer.echo(f"  - {p}")
    raise typer.Exit(code=1)
