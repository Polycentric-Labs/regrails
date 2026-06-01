"""RegRails CLI root — wires sub-apps + the pure ``decide`` and ``coverage`` commands."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from ..audit import EventAction, append_decision, emit_event
from ..encode import load_all_rules
from ..guardrail import ConsultationRequest, decide
from .audit_cli import app as audit_app
from .check_cli import app as check_app
from .coverage_cli import app as coverage_app
from .encode_cli import app as encode_app
from .report_cli import app as report_app
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
app.add_typer(audit_app, name="audit", help="Verify decision-provenance logs.")
app.add_typer(coverage_app, name="coverage", help="Rule-to-scenario coverage matrix.")
app.add_typer(report_app, name="report", help="Render a static HTML decision report.")


@app.command("decide")
def decide_cmd(
    query: str = typer.Option(..., "--query", "-q", help="The user-facing query."),
    topic: str = typer.Option("unknown", help="disclosure | aid_status | other | unknown"),
    requester_role: str = typer.Option("unknown", "--role"),
    purpose: str = typer.Option("unknown"),
    data: str = typer.Option("", "--data", help="Comma-separated data_requested items."),
    consent_on_file: bool = typer.Option(False, "--consent-on-file"),
    opted_out: bool = typer.Option(False, "--opted-out", help="Student opted out of directory info."),
    emergency_justified: bool = typer.Option(False, "--emergency-justified"),
    safe_harbor: str = typer.Option("", "--safe-harbor", help="Comma-separated conditions met."),
    redisclosing: bool = typer.Option(False, "--redisclosing"),
    aggregate: bool = typer.Option(False, "--aggregate", help="Aggregate / de-identified."),
    aid_determination: bool = typer.Option(False, "--aid-determination"),
    sap_status: str = typer.Option("unknown", "--sap-status"),
    in_default: bool | None = typer.Option(None, "--in-default/--no-in-default"),
    appeal_basis: bool = typer.Option(False, "--appeal-basis"),
    log: Path | None = typer.Option(None, "--log", help="Append the decision to a hash-chained log."),
) -> None:
    """Run the DETERMINISTIC guardrail engine (no LLM) and print the GuardrailDecision.

    This is the governance boundary as a testable artifact: the decision is made
    entirely by the rule engine. The LLM (see the demo) only renders the reply.
    """
    req = ConsultationRequest(
        query=query,
        topic=topic,  # type: ignore[arg-type]
        requester_role=requester_role,  # type: ignore[arg-type]
        purpose=purpose,  # type: ignore[arg-type]
        data_requested=[d.strip() for d in data.split(",") if d.strip()],
        consent_on_file=consent_on_file,
        student_opted_out_of_directory=opted_out,
        emergency_justified=emergency_justified,
        safe_harbor_conditions_met=[s.strip() for s in safe_harbor.split(",") if s.strip()],
        receiver_redisclosing=redisclosing,
        aggregate_or_de_identified=aggregate,
        aid_determination_requested=aid_determination,
        sap_status=sap_status,  # type: ignore[arg-type]
        student_in_default=in_default,
        appeal_basis_present=appeal_basis,
    )
    decision = decide(req, load_all_rules())
    payload = decision.model_dump(mode="json")
    typer.echo(json.dumps(payload, indent=2))

    if log is not None:
        record_hash = append_decision(payload, log)
        emit_event(
            EventAction.DECISION_RECORDED,
            payload={"decision_id": decision.id, "record_hash": record_hash, "log": str(log)},
        )
        typer.echo(f"\nAppended to hash-chained log {log} (record_hash={record_hash[:16]}...).")


if __name__ == "__main__":  # pragma: no cover
    app()
