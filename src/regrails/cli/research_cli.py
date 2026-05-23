"""``regrails research`` sub-app — run Perplexity Sonar streams via OpenRouter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import typer

from ..research import run_research_stream

app = typer.Typer(help="Run Perplexity Sonar research streams.", no_args_is_help=True)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SNAPSHOTS_DIR = PROJECT_ROOT / "research" / "snapshots"


@app.command("run")
def run(
    stream_name: str = typer.Argument(..., help="Slug, e.g. 'ferpa-ai-ambiguities'."),
    query: str = typer.Option(..., "--query", "-q", help="The Sonar prompt."),
    model: str = typer.Option(
        "perplexity/sonar-pro", "--model", "-m", help="OpenRouter model id."
    ),
    out_dir: Path | None = typer.Option(
        None,
        "--out-dir",
        help="Directory to write the snapshot to. Defaults to research/snapshots/<YYYY-MM-DD>/.",
    ),
) -> None:
    """Run one research stream and persist the snapshot JSON to disk."""
    snapshot = run_research_stream(stream_name=stream_name, query=query, model=model)

    target_dir = out_dir or SNAPSHOTS_DIR / datetime.now(UTC).strftime("%Y-%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{snapshot.id}.json"
    target.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    typer.echo(f"Wrote {target} ({len(snapshot.response_text)} chars).")
    if snapshot.cost_usd is not None:
        typer.echo(f"Cost: ${snapshot.cost_usd:.4f}")
