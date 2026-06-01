"""CLI smoke tests via Typer's CliRunner (v0.2 — FERPA + Title IV)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from regrails.cli.main import app

runner = CliRunner()


def test_root_help_lists_all_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for sub in ("check", "encode", "research", "audit", "coverage", "decide"):
        assert sub in result.stdout


def test_check_faithfulness_passes_all_frameworks() -> None:
    result = runner.invoke(app, ["check", "faithfulness"])
    assert result.exit_code == 0, result.stdout
    assert "37/37 rules passed" in result.stdout


def test_encode_list_includes_all_rules() -> None:
    result = runner.invoke(app, ["encode", "list"])
    assert result.exit_code == 0
    assert "FERPA-99.30-1" in result.stdout
    assert "TIV-668.34-A7" in result.stdout
    assert "37 rules across 8 sections" in result.stdout


def test_encode_list_json_emits_37() -> None:
    result = runner.invoke(app, ["encode", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 37


def test_encode_list_title_iv_only() -> None:
    result = runner.invoke(app, ["encode", "list", "--framework", "Title IV"])
    assert result.exit_code == 0
    assert "TIV-668.34-A7" in result.stdout
    assert "FERPA-99.30-1" not in result.stdout


def test_decide_ferpa_block_json() -> None:
    result = runner.invoke(app, ["decide", "-q", "What's Jane's GPA?", "--data", "gpa"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "block"
    assert payload["framework"] == "FERPA"
    assert payload["human_gate_required"] is False


def test_decide_title_iv_human_gate_json() -> None:
    result = runner.invoke(
        app,
        [
            "decide", "-q", "I defaulted; am I eligible?",
            "--topic", "aid_status", "--aid-determination", "--in-default",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "escalate_human_review"
    assert payload["framework"] == "Title IV"
    assert payload["risk_tier"] == "high"
    assert payload["human_gate_required"] is True


def test_decide_log_then_audit_verify(tmp_path: Path) -> None:
    log = tmp_path / "decisions.jsonl"
    for q in ("What's the GPA?", "Roster please"):
        r = runner.invoke(app, ["decide", "-q", q, "--data", "gpa", "--log", str(log)])
        assert r.exit_code == 0
    verify = runner.invoke(app, ["audit", "verify", str(log)])
    assert verify.exit_code == 0
    assert "hash chain intact" in verify.stdout


def test_coverage_report_stdout() -> None:
    result = runner.invoke(app, ["coverage", "report"])
    assert result.exit_code == 0
    assert "coverage matrix" in result.stdout
    assert "FERPA-99.30-1" in result.stdout


def test_report_html_written(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["report", "html", "--out", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "RegRails" in text
    assert 'class="card"' in text
