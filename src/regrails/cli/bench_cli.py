"""``regrails bench`` sub-app — run + report the with/without-guardrail benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from ..bench import BenchRow
from ..bench.judge import JUDGE_MODEL_DEFAULT
from ..bench.report import aggregate, to_eval_md
from ..bench.runner import run_benchmark

app = typer.Typer(help="With/without-guardrail benchmark (pilot).", no_args_is_help=True)

DEFAULT_MODELS = [
    "openai/gpt-5.5",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.3",
    "deepseek/deepseek-v4-pro",
]
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCEN = _ROOT / "bench" / "scenarios.heldout.jsonl"
_RESULTS = _ROOT / "bench" / "results.jsonl"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.command("run")
def run(
    scenarios: Path = typer.Option(_SCEN, "--scenarios"),
    models: str = typer.Option(",".join(DEFAULT_MODELS), "--models", help="Comma-separated OpenRouter ids."),
    judge_model: str = typer.Option(JUDGE_MODEL_DEFAULT, "--judge-model"),
    out: Path = typer.Option(_RESULTS, "--out"),
) -> None:
    """LIVE: query each model with + without the guardrail (needs OPENROUTER_API_KEY)."""
    scen = _load_jsonl(scenarios)
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    typer.echo(
        f"Running {len(scen)} scenarios x {len(model_list)} models (judge: {judge_model}) ...",
        err=True,
    )

    def progress(sid: str, model: str) -> None:
        typer.echo(f"  {sid} / {model}", err=True)

    rows = run_benchmark(scen, model_list, judge_model=judge_model, progress=progress)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fp:
        for r in rows:
            fp.write(json.dumps(r.to_dict()) + "\n")
    typer.echo(f"Wrote {len(rows)} rows to {out}")


@app.command("report")
def report(
    results: Path = typer.Option(_RESULTS, "--results"),
    judge_model: str = typer.Option(JUDGE_MODEL_DEFAULT, "--judge-model"),
    out: Path | None = typer.Option(None, "--out", help="Write the EVAL.md here."),
) -> None:
    """Aggregate results.jsonl into the EVAL report (per-model, Wilson CI, kappa)."""
    rows = [BenchRow(**r) for r in _load_jsonl(results)]
    n_scen = len({r.scenario_id for r in rows})
    md = to_eval_md(aggregate(rows), rows, scenario_count=n_scen, judge_model=judge_model)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote {out}")
    else:
        typer.echo(md)
