"""CLI smoke tests via Typer's CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from regrails.cli.main import app

runner = CliRunner()


def test_root_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "check" in result.stdout
    assert "encode" in result.stdout
    assert "research" in result.stdout


def test_check_faithfulness_passes() -> None:
    result = runner.invoke(app, ["check", "faithfulness"])
    assert result.exit_code == 0, result.stdout
    assert "23/23 rules passed" in result.stdout


def test_check_faithfulness_verbose_includes_table() -> None:
    result = runner.invoke(app, ["check", "faithfulness", "--verbose"])
    assert result.exit_code == 0
    assert "FERPA-99.30-1" in result.stdout
    assert "FERPA-99.37-E" in result.stdout


def test_encode_list_includes_all_rules() -> None:
    result = runner.invoke(app, ["encode", "list"])
    assert result.exit_code == 0
    assert "FERPA-99.30-1" in result.stdout
    assert "23 rules across 6 sections" in result.stdout


def test_encode_list_json_emits_json() -> None:
    import json

    result = runner.invoke(app, ["encode", "list", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 23


def test_encode_verify_runs() -> None:
    result = runner.invoke(app, ["encode", "verify"])
    assert result.exit_code == 0
    assert "Loaded OK" in result.stdout
