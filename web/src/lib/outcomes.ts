/*
 * Outcome → color and risk → color maps for RegRails. These reproduce the
 * engine-semantic palette from the original web/index.html demo (already
 * consistent with the engine's own semantics) so the SPA stays visually true
 * to the CLI/decision colors.
 *
 * Two views are exported:
 *   - *_VAR maps return CSS var() references (theme-aware: light/dark swap via
 *     tokens.css) — use these in JSX style props.
 *   - *_HEX maps return the literal light-mode hex — use where a concrete color
 *     string is required (Recharts series, canvas, tests).
 */

export type Outcome =
  | "allow"
  | "block"
  | "escalate_consent"
  | "escalate_directory_check"
  | "escalate_human_review"
  | "insufficient_facts"
  | "out_of_scope";

export type RiskTier = "low" | "medium" | "high";

/** Light-mode literal hex (mirrors the original demo palette exactly). */
export const OUTCOME_HEX: Record<Outcome, string> = {
  allow: "#1a7f37",
  block: "#b91c1c",
  escalate_consent: "#b45309",
  escalate_directory_check: "#b45309",
  escalate_human_review: "#7c3aed",
  insufficient_facts: "#6b7280",
  out_of_scope: "#2563eb",
};

export const RISK_HEX: Record<RiskTier, string> = {
  low: "#1a7f37",
  medium: "#b45309",
  high: "#b91c1c",
};

/** Theme-aware var() references (defined in tokens.css, swap on .dark). */
export const OUTCOME_VAR: Record<Outcome, string> = {
  allow: "var(--outcome-allow)",
  block: "var(--outcome-block)",
  escalate_consent: "var(--outcome-escalate-consent)",
  escalate_directory_check: "var(--outcome-escalate-directory)",
  escalate_human_review: "var(--outcome-escalate-human)",
  insufficient_facts: "var(--outcome-insufficient)",
  out_of_scope: "var(--outcome-out-of-scope)",
};

export const RISK_VAR: Record<RiskTier, string> = {
  low: "var(--risk-low)",
  medium: "var(--risk-medium)",
  high: "var(--risk-high)",
};

const NEUTRAL = "#374151";

/** Theme-aware color for an outcome; falls back to neutral for unknown values. */
export function outcomeColor(outcome: string): string {
  return OUTCOME_VAR[outcome as Outcome] ?? NEUTRAL;
}

/** Theme-aware color for a risk tier; falls back to neutral. */
export function riskColor(risk: string): string {
  return RISK_VAR[risk as RiskTier] ?? NEUTRAL;
}

/** Literal hex for an outcome (for Recharts/canvas/tests). */
export function outcomeHex(outcome: string): string {
  return OUTCOME_HEX[outcome as Outcome] ?? NEUTRAL;
}

/** Literal hex for a risk tier (for Recharts/canvas/tests). */
export function riskHex(risk: string): string {
  return RISK_HEX[risk as RiskTier] ?? NEUTRAL;
}

/** Human-readable label for an outcome (lower_snake → Title Case). */
export function outcomeLabel(outcome: string): string {
  return outcome
    .split("_")
    .map((w) => (w.length ? w[0]!.toUpperCase() + w.slice(1) : w))
    .join(" ");
}
