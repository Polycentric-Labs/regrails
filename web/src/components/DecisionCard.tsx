import type { CSSProperties, ReactNode } from "react";
import type { GuardrailDecision } from "../lib/api";
import { riskColor } from "../lib/outcomes";
import { Card, CardBody, CardHead } from "../ui/Card";
import Badge from "../ui/Badge";
import OutcomeBadge from "./OutcomeBadge";

/** Label-column / value-column grid for the decision fields (token-driven). */
const DL_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(8rem, max-content) 1fr",
  gap: "0.55rem 1rem",
  alignItems: "baseline",
  margin: 0,
};

/** One `<dt>`/`<dd>` row inside the decision field grid. */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt
        className="muted"
        style={{
          fontSize: "0.68rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </dt>
      <dd style={{ margin: 0 }}>{children}</dd>
    </>
  );
}

export interface DecisionCardProps {
  /** The authoritative engine verdict from /api/decide (or /api/reply). */
  decision: GuardrailDecision;
  /**
   * Whether this decision intercepted the request (anything other than allow /
   * out_of_scope). Drives the destructive accent so a gate reads at a glance.
   * Defaults to derived-from-outcome when omitted.
   */
  intercepted?: boolean;
  /** Optional trailing content rendered under the decision (e.g. the replies). */
  children?: ReactNode;
}

/** Outcomes that should NOT carry the destructive (red) card accent. */
const ALLOWED_OUTCOMES = new Set(["allow", "out_of_scope"]);

/**
 * True when the decision intercepted the request — any outcome outside
 * ALLOWED_OUTCOMES — so the card carries the destructive accent. An explicit
 * `override` (the `intercepted` prop) wins over the derived value.
 */
function isIntercept(decision: GuardrailDecision, override?: boolean): boolean {
  if (typeof override === "boolean") return override;
  return !ALLOWED_OUTCOMES.has(decision.outcome);
}

/** Pull the engine's operator-readable reasoning, whatever field it lands in. */
function engineReasoning(decision: GuardrailDecision): string {
  const rationale =
    typeof decision.rationale === "string" ? decision.rationale.trim() : "";
  if (rationale) return rationale;
  const llm =
    typeof decision.llm_response === "string" ? decision.llm_response.trim() : "";
  return llm;
}

/**
 * The headline artifact: the deterministic engine's verdict, rendered before
 * any model speaks. Outcome + risk + (conditional) human-gate badges up top,
 * then the framework, the emitted CFR citations as monospace chips, the matched
 * rule ids, and the engine's own reasoning. `children` (the guarded/unguarded
 * replies) render beneath, so the card always stands on its own even when the
 * advisor reply is unavailable.
 */
export function DecisionCard({
  decision,
  intercepted,
  children,
}: DecisionCardProps) {
  const gate = decision.human_gate_required;
  const blocked = isIntercept(decision, intercepted);
  const citations = decision.citations_emitted ?? [];
  const rules = decision.matched_rules ?? [];
  const reasoning = engineReasoning(decision);

  return (
    <Card
      variant={blocked ? "dest" : "prim"}
      accentTop
      className="decision-card"
    >
      <CardHead>
        <div className="row-between wrap gap-3">
          <h3 className="card-title" data-testid="decision-title">
            Engine decision
          </h3>
          <span className="muted mono" style={{ fontSize: "0.74rem" }}>
            deterministic · pre-LLM
          </span>
        </div>
        <div
          className="row wrap gap-2"
          data-testid="decision-badges"
          style={{ marginTop: "0.15rem" }}
        >
          <OutcomeBadge outcome={decision.outcome} />
          <Badge
            color={riskColor(decision.risk_tier)}
            dot
            title={`risk tier: ${decision.risk_tier}`}
          >
            Risk: {decision.risk_tier}
          </Badge>
          {gate && (
            <span data-testid="human-gate" className="row">
              <Badge
                color="var(--outcome-escalate-human)"
                solid
                className="cap"
                title="A human decision-maker must make this call"
              >
                Human gate
              </Badge>
            </span>
          )}
        </div>
      </CardHead>

      <CardBody flush>
        <div className="stack-4">
          <dl style={DL_STYLE}>
            <Field label="Framework">
              <Badge title="Regulatory framework the decision was made under">
                {decision.framework}
              </Badge>
            </Field>

            <Field label="Citations emitted">
              {citations.length > 0 ? (
                <span className="row wrap gap-2" data-testid="citations">
                  {citations.map((c) => (
                    <code className="code-chip" key={c}>
                      {c}
                    </code>
                  ))}
                </span>
              ) : (
                <span className="faint">none</span>
              )}
            </Field>

            <Field label="Matched rules">
              {rules.length > 0 ? (
                <span className="row wrap gap-2" data-testid="matched-rules">
                  {rules.map((r) => (
                    <code className="code-chip" key={r}>
                      {r}
                    </code>
                  ))}
                </span>
              ) : (
                <span className="faint">none</span>
              )}
            </Field>
          </dl>

          {reasoning && (
            <div className="box" data-testid="engine-reasoning">
              <div
                className="muted mono"
                style={{ fontSize: "0.7rem", marginBottom: "0.3rem" }}
              >
                ENGINE REASONING
              </div>
              <p style={{ margin: 0, fontSize: "0.88rem", lineHeight: 1.55 }}>
                {reasoning}
              </p>
            </div>
          )}

          {children}
        </div>
      </CardBody>
    </Card>
  );
}

export default DecisionCard;
