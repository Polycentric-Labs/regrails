"""RegRails CLI root — wires sub-apps under one ``regrails`` entry point."""

from __future__ import annotations

import typer

from .check_cli import app as check_app
from .encode_cli import app as encode_app
from .research_cli import app as research_app

app = typer.Typer(
    name="regrails",
    help="RegRails — codify federal regulations into machine-readable rules.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(check_app, name="check", help="Faithfulness + validation checks.")
app.add_typer(encode_app, name="encode", help="Encoding inspection commands.")
app.add_typer(research_app, name="research", help="Run Perplexity Sonar research streams.")


if __name__ == "__main__":  # pragma: no cover
    app()
