"""LLM call helper with retry + provider fallback.

Wraps :func:`regrails.research.chat_completion`. The advisor demo calls
``advisor_render`` after the guardrail has emitted a decision; this is the
LLM's only job in the POC — render the user-facing text the advisor would
actually send. Decision logic stays deterministic in
:mod:`regrails.guardrail`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import cast

import httpx

from .audit import EventAction, emit_event
from .models import GuardrailDecision
from .research import chat_completion

DEFAULT_PRIMARY_MODEL = "anthropic/claude-3.5-haiku"
DEFAULT_FALLBACK_MODELS: tuple[str, ...] = ("openai/gpt-4o-mini",)
DEFAULT_RETRY_COUNT = 2


_ADVISOR_SYSTEM_PROMPT = """\
You are a student-services advisor at an example U.S. institution (synthetic). A \
policy rule engine (RegRails) has already consulted on the incoming query and \
produced a structured GuardrailDecision covering FERPA (student records) or \
Title IV (federal financial aid). Your job is to render the SINGLE user-facing \
reply for the advisor to send. The engine decides; you only phrase the reply.

Respond per the decision's outcome:
- allow: answer concisely. If the decision describes a recordkeeping or audit \
  obligation, surface it as a follow-up instruction for staff (not the user). \
  For Title IV, explain the rule in general terms; never promise a specific \
  student's aid.
- block: refuse the request. Cite the section numbers from citations_emitted. \
  Briefly explain WHY in plain English. Do not lecture.
- escalate_consent: explain what specific written consent or contractual \
  condition must be in place. Do NOT answer the underlying question.
- escalate_directory_check: explain that per-student opt-out status must be \
  confirmed first. Do NOT answer the underlying question.
- escalate_human_review: this is a high-stakes, effectively irreversible \
  determination (loss of aid eligibility, loan default, eligibility yes/no). \
  Do NOT give an answer; explain warmly that a financial-aid officer (a human) \
  must make this decision, and tell the student exactly who to contact and why.
- insufficient_facts: explain what specific facts are missing before anyone can \
  assess this, and how to obtain them. Do NOT guess an answer.
- out_of_scope: this is not a regulated records/aid matter; answer the question \
  normally and briefly, with no compliance ceremony.

Hard rules: keep the response to 3-5 sentences. Never invent or disclose any \
actual student data (synthetic demo). Be warm but precise. Use plain English; \
no markdown. Address the asker in second person."""


def advisor_render(
    *,
    query: str,
    decision: GuardrailDecision,
    primary_model: str = DEFAULT_PRIMARY_MODEL,
    fallback_models: tuple[str, ...] = DEFAULT_FALLBACK_MODELS,
    retry_count: int = DEFAULT_RETRY_COUNT,
    api_key: str | None = None,
    audit_sink: Path | None = None,
    http_client: httpx.Client | None = None,
) -> tuple[str, str]:
    """Render the user-facing advisor reply for a given decision.

    Returns ``(text, model_used)``. Tries ``primary_model`` first, retries on
    transient failure, then falls back through ``fallback_models``. Raises if
    every option fails.
    """
    decision_json = json.dumps(decision.model_dump(mode="json"), indent=2)
    user_msg = (
        f"User's original query:\n{query}\n\n"
        f"RegRails GuardrailDecision:\n```json\n{decision_json}\n```\n\n"
        f"Render the single advisor reply per your system instructions."
    )

    models_to_try = (primary_model, *fallback_models)
    last_exc: Exception | None = None

    for model in models_to_try:
        for attempt in range(retry_count + 1):
            try:
                resp = chat_completion(
                    model=model,
                    messages=[
                        {"role": "system", "content": _ADVISOR_SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    api_key=api_key,
                    http_client=http_client,
                )
                choices = resp.get("choices") or []
                if choices:
                    text = (choices[0].get("message") or {}).get("content") or ""
                    if text.strip():
                        if audit_sink is not None:
                            emit_event(
                                EventAction.LLM_CALL_SUCCEEDED,
                                payload={
                                    "model": model,
                                    "decision_id": decision.id,
                                    "attempt": attempt,
                                    "chars": len(text),
                                },
                                sink=audit_sink,
                            )
                            if model != primary_model:
                                emit_event(
                                    EventAction.LLM_FALLBACK_USED,
                                    payload={"used_model": model, "primary": primary_model},
                                    sink=audit_sink,
                                )
                        return cast(str, text), model
                # empty content — treat as failure, retry
                raise RuntimeError(f"empty content from {model}")
            except Exception as exc:
                last_exc = exc
                if audit_sink is not None:
                    emit_event(
                        EventAction.LLM_CALL_FAILED,
                        payload={
                            "model": model,
                            "decision_id": decision.id,
                            "attempt": attempt,
                            "error": str(exc)[:300],
                        },
                        sink=audit_sink,
                    )
                # Exponential backoff before next attempt on same model.
                if attempt < retry_count:
                    time.sleep(0.5 * (2**attempt))
        # move to next model
        continue

    raise RuntimeError(
        f"all models exhausted ({models_to_try!r}): last error = {last_exc!r}"
    )
