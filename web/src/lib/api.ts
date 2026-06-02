/*
 * Typed POST helpers for the three RegRails serverless functions:
 *   /api/decide  — deterministic engine, no key, always works (web/api/decide.py)
 *   /api/verify  — audit hash-chain verifier, no key (web/api/verify.py — B2)
 *   /api/reply   — optional engine-gated live LLM reply (web/api/reply.py — B2)
 *
 * These wrap fetch + JSON only. Always-degrade behavior (render the engine
 * decision even when /api/reply errors) is the calling route's responsibility;
 * postJson surfaces a typed ApiError the route can catch.
 */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function postJson<TReq, TRes>(
  path: string,
  payload: TReq,
  init?: RequestInit,
): Promise<TRes> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify(payload),
    ...init,
  });
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    // Non-JSON body (e.g. an HTML 500 page) — leave body null.
  }
  if (!res.ok) {
    const msg =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `Request to ${path} failed (HTTP ${res.status})`;
    throw new ApiError(res.status, msg, body);
  }
  return body as TRes;
}

/* ── /api/decide ─────────────────────────────────────────────────────── */

/**
 * Consultation request — mirrors regrails.guardrail.ConsultationRequest. All
 * structured fields are optional; only `query` is conventional. Enum-typed
 * string fields are kept as `string` here (the engine validates and returns a
 * 400 on a bad enum, which postJson surfaces as an ApiError).
 */
export interface ConsultationRequest {
  query: string;
  topic?: string;
  requester_role?: string;
  purpose?: string;
  sap_status?: string;
  /** Comma-joined string OR string[]; decide.py normalizes both. */
  data_requested?: string | string[];
  aid_determination_requested?: boolean;
  student_in_default?: boolean;
  consent_on_file?: boolean;
  student_opted_out_of_directory?: boolean;
  emergency_justified?: boolean;
  [key: string]: unknown;
}

/** GuardrailDecision — the engine's typed verdict (model_dump shape). */
export interface GuardrailDecision {
  outcome: string;
  risk_tier: string;
  framework: string;
  human_gate_required: boolean;
  citations_emitted: string[];
  matched_rules: string[];
  llm_response?: string | null;
  rationale?: string | null;
  [key: string]: unknown;
}

export interface ApiErrorBody {
  error: string;
}

/** Run the deterministic guardrail. No API key required; always available. */
export function decide(
  req: ConsultationRequest,
  init?: RequestInit,
): Promise<GuardrailDecision> {
  return postJson<ConsultationRequest, GuardrailDecision>(
    "/api/decide",
    req,
    init,
  );
}

/* ── /api/verify ─────────────────────────────────────────────────────── */

export interface VerifyRequest {
  /** Raw JSONL text of a hash-chained decision log to verify. */
  log: string;
}

export interface VerifyResponse {
  ok: boolean;
  problems: string[];
}

/** Verify a pasted audit hash-chain (reuses regrails.audit; CLI-parity). */
export function verify(
  log: string,
  init?: RequestInit,
): Promise<VerifyResponse> {
  return postJson<VerifyRequest, VerifyResponse>("/api/verify", { log }, init);
}

/* ── /api/reply ──────────────────────────────────────────────────────── */

export interface ReplyResponse {
  /** The authoritative engine decision (computed server-side first). */
  decision: GuardrailDecision;
  /** Guarded reply: model-rendered (allow/out_of_scope) or templated. */
  guarded_reply: string;
  /** Which model rendered the reply, or null if templated / degraded. */
  model_used: string | null;
}

/**
 * Optional engine-gated live LLM reply. The engine decides first; only certain
 * outcomes call the model. Always returns the decision even when the LLM is
 * unavailable (the route should still catch ApiError for transport failures).
 */
export function reply(
  req: ConsultationRequest,
  init?: RequestInit,
): Promise<ReplyResponse> {
  return postJson<ConsultationRequest, ReplyResponse>("/api/reply", req, init);
}
