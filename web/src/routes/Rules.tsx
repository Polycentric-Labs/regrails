/**
 * `/rules` — Rules browser. A searchable, filterable reference table over the 37
 * compiled rules in data/rules.json (FERPA Subpart D + Title IV eligibility).
 *
 * The engine's rule corpus is the product's spine, so this route reads like a
 * real regulatory reference: framework filter, free-text search across citation
 * + plain-language text, a live shown/total count, a sticky table header, and a
 * row that expands to the VERBATIM CFR section text plus the content hash the
 * engine pins each rule to. Presentation only — every field is rendered straight
 * from the generated JSON (loadData), never recomputed client-side.
 */
import { useEffect, useMemo, useState } from "react";
import { loadData } from "../lib/data";
import { riskColor } from "../lib/outcomes";
import Badge from "../ui/Badge";
import Button from "../ui/Button";
import CodeBlock from "../ui/CodeBlock";

/** One rule, exactly as gen_web_data.py dumps it (see public/data/rules.json). */
interface Rule {
  id: string;
  framework: string;
  citation: string;
  citation_url: string;
  rule_type: string;
  /** "block" | "escalate" | "warn" — engine action class. */
  severity: string;
  /** null for FERPA rows; "low" | "medium" | "high" for Title IV. */
  risk_tier: string | null;
  /** True when the rule routes to a human gate rather than auto-deciding. */
  human_gate: boolean;
  /** Plain-language restatement of the rule. */
  text: string;
  rationale: string;
  section_id: string;
  section_title: string;
  /** Verbatim CFR section body (newline-delimited). Rendered as a text node. */
  section_text: string;
  /** SHA-256 the engine pins the section text to. */
  section_hash: string;
  source_quote: string;
}

interface RulesFile {
  rules: Rule[];
}

type Framework = "All" | "FERPA" | "Title IV";
const FRAMEWORKS: Framework[] = ["All", "FERPA", "Title IV"];

/** Tint a severity word with the closest engine-semantic color. */
function severityColor(severity: string): string {
  switch (severity) {
    case "block":
      return "var(--outcome-block)";
    case "escalate":
      return "var(--outcome-escalate-human)";
    case "warn":
      return "var(--outcome-escalate-consent)";
    default:
      return "var(--fg-muted)";
  }
}

/** lower_snake / "Title IV" → human label, leaving already-spaced text intact. */
function titleCase(value: string): string {
  return value
    .split("_")
    .map((w) => (w.length ? w[0]!.toUpperCase() + w.slice(1) : w))
    .join(" ");
}

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; rules: Rule[] };

export default function Rules() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [framework, setFramework] = useState<Framework>("All");
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadData<RulesFile>("rules")
      .then((data) => {
        if (alive) setState({ status: "ready", rules: data.rules });
      })
      .catch((err: unknown) => {
        if (alive) {
          setState({
            status: "error",
            message:
              err instanceof Error ? err.message : "Failed to load rules.",
          });
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  const allRules = useMemo(
    () => (state.status === "ready" ? state.rules : []),
    [state],
  );

  // Framework + free-text search. Search matches citation + plain-language text
  // (case-insensitive), which is how an operator hunts a rule in practice.
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return allRules.filter((r) => {
      if (framework !== "All" && r.framework !== framework) return false;
      if (!q) return true;
      return (
        r.citation.toLowerCase().includes(q) ||
        r.text.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
      );
    });
  }, [allRules, framework, query]);

  const total = allRules.length;

  // Per-framework counts for the filter chips (computed once data is ready).
  const counts = useMemo(() => {
    const c: Record<Framework, number> = { All: total, FERPA: 0, "Title IV": 0 };
    for (const r of allRules) {
      if (r.framework === "FERPA") c.FERPA += 1;
      else if (r.framework === "Title IV") c["Title IV"] += 1;
    }
    return c;
  }, [allRules, total]);

  return (
    <section className="page" data-route="rules">
      <header className="stack-2" style={{ marginBottom: "1.25rem" }}>
        <h1 className="page-title">Rules</h1>
        <p className="page-sub">
          The 37 deterministic rules the engine evaluates before any model
          speaks — FERPA Subpart D (the consent regime) plus Title IV student-aid
          eligibility. Each is pinned to a verbatim slice of the Code of Federal
          Regulations and its content hash. Filter by framework or search the
          citation and plain-language text; click any row for the source text.
        </p>
      </header>

      {state.status === "loading" && (
        <div className="box" role="status" aria-live="polite">
          <span className="muted">Loading rules…</span>
        </div>
      )}

      {state.status === "error" && (
        <div className="alert destructive" role="alert">
          <div className="alert-body">
            <p className="alert-title">Couldn’t load the rule corpus</p>
            <p className="alert-desc">{state.message}</p>
          </div>
        </div>
      )}

      {state.status === "ready" && (
        <div className="stack-4">
          {/* ── Controls: framework filter + search + live count ── */}
          <div
            className="row-between wrap gap-3"
            role="search"
            aria-label="Filter rules"
          >
            <div
              className="row gap-2"
              role="group"
              aria-label="Framework filter"
            >
              {FRAMEWORKS.map((f) => (
                <Button
                  key={f}
                  variant={framework === f ? "default" : "outline"}
                  size="sm"
                  aria-pressed={framework === f}
                  onClick={() => setFramework(f)}
                >
                  {f}
                  <span
                    className="tnum"
                    style={{ opacity: 0.7, marginLeft: "0.1rem" }}
                  >
                    {counts[f]}
                  </span>
                </Button>
              ))}
            </div>

            <div className="row gap-3 wrap">
              <input
                className="input"
                type="search"
                inputMode="search"
                placeholder="Search citation or rule text…"
                aria-label="Search rules"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ width: "min(20rem, 60vw)" }}
              />
              <span
                className="muted tnum"
                aria-live="polite"
                style={{ whiteSpace: "nowrap", fontSize: "0.85rem" }}
              >
                Showing <b data-testid="shown-count">{shown.length}</b> of{" "}
                <b data-testid="total-count">{total}</b>
              </span>
            </div>
          </div>

          {/* ── Reference table (sticky header, hover rows, expandable) ── */}
          <div
            className="table-wrap"
            style={{ maxHeight: "calc(100vh - 320px)", overflowY: "auto" }}
          >
            <table className="tbl" data-testid="rules-table">
              <thead style={{ position: "sticky", top: 0, zIndex: 1 }}>
                <tr>
                  <th scope="col" style={{ width: "9rem" }}>
                    Framework
                  </th>
                  <th scope="col">Citation</th>
                  <th scope="col">Rule</th>
                  <th scope="col" style={{ width: "7rem" }}>
                    Risk tier
                  </th>
                  <th scope="col" style={{ width: "6.5rem" }}>
                    Severity
                  </th>
                  <th scope="col" style={{ width: "6rem", textAlign: "center" }}>
                    Human gate
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.length === 0 && (
                  <tr>
                    <td colSpan={6} className="muted" style={{ padding: "1rem" }}>
                      No rules match “{query}”
                      {framework !== "All" ? ` in ${framework}` : ""}.
                    </td>
                  </tr>
                )}

                {shown.map((r) => {
                  const open = openId === r.id;
                  return (
                    <RuleRows
                      key={r.id}
                      rule={r}
                      open={open}
                      onToggle={() => setOpenId(open ? null : r.id)}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>

          <p className="faint" style={{ fontSize: "0.78rem" }}>
            Source text is the verbatim Code of Federal Regulations; the hash is
            the SHA-256 the engine pins each section to. Synthetic demo — not
            legal advice.
          </p>
        </div>
      )}
    </section>
  );
}

/**
 * A rule's summary row plus (when open) its detail row. Kept as a sub-component
 * so the expand state reads cleanly and the detail panel can span all columns.
 */
function RuleRows({
  rule,
  open,
  onToggle,
}: {
  rule: Rule;
  open: boolean;
  onToggle: () => void;
}) {
  const tier = rule.risk_tier;
  const detailId = `rule-detail-${rule.id}`;

  return (
    <>
      <tr
        data-testid="rule-row"
        data-rule-id={rule.id}
        data-framework={rule.framework}
        onClick={onToggle}
        style={{ cursor: "pointer" }}
        aria-expanded={open}
      >
        <td>
          <span className="muted" style={{ fontSize: "0.82rem" }}>
            {rule.framework}
          </span>
        </td>
        <td>
          <button
            type="button"
            className="primary-link"
            onClick={(e) => {
              e.stopPropagation();
              onToggle();
            }}
            aria-expanded={open}
            aria-controls={detailId}
            style={{
              background: "none",
              border: "none",
              padding: 0,
              cursor: "pointer",
              font: "inherit",
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
            }}
          >
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                transition: "transform .12s",
                transform: open ? "rotate(90deg)" : "none",
                opacity: 0.6,
                fontSize: "0.7rem",
              }}
            >
              ▶
            </span>
            <span className="mono" style={{ fontSize: "0.82rem" }}>
              {rule.citation}
            </span>
          </button>
        </td>
        <td>
          <span style={{ display: "block", maxWidth: "52ch" }}>{rule.text}</span>
        </td>
        <td>
          {tier ? (
            <Badge color={riskColor(tier)} dot capitalize>
              {tier}
            </Badge>
          ) : (
            <span className="faint" title="No risk tier (FERPA consent regime)">
              —
            </span>
          )}
        </td>
        <td>
          <Badge color={severityColor(rule.severity)} capitalize>
            {rule.severity}
          </Badge>
        </td>
        <td style={{ textAlign: "center" }}>
          {rule.human_gate ? (
            <Badge color="var(--outcome-escalate-human)" title="Routes to a human gate">
              Yes
            </Badge>
          ) : (
            <span className="faint">—</span>
          )}
        </td>
      </tr>

      {open && (
        <tr data-testid="rule-detail-row">
          <td colSpan={6} style={{ padding: 0 }}>
            <div
              id={detailId}
              className="stack-3"
              style={{
                padding: "1rem 1.1rem 1.25rem",
                background: "hsl(var(--surface-2) / 0.5)",
                borderTop: "1px solid hsl(var(--border))",
              }}
            >
              <div className="row-between wrap gap-3">
                <div className="stack-2">
                  <span className="h2" style={{ fontSize: "1.02rem" }}>
                    § {rule.section_id.replace(/^34-CFR-/, "")} —{" "}
                    {rule.section_title}
                  </span>
                  <div className="row gap-2 wrap">
                    <Badge>{titleCase(rule.rule_type)}</Badge>
                    <span className="muted" style={{ fontSize: "0.8rem" }}>
                      Rule ID{" "}
                      <span className="mono">{rule.id}</span>
                    </span>
                  </div>
                </div>
                <a
                  className="primary-link"
                  href={rule.citation_url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{ fontSize: "0.85rem" }}
                >
                  View on Cornell LII ↗
                </a>
              </div>

              <div className="box" style={{ background: "hsl(var(--surface))" }}>
                <p
                  className="muted"
                  style={{ margin: "0 0 0.35rem", fontSize: "0.78rem" }}
                >
                  Why this rule exists
                </p>
                <p style={{ margin: 0, fontSize: "0.88rem", lineHeight: 1.55 }}>
                  {rule.rationale}
                </p>
              </div>

              <CodeBlock
                label={`Verbatim CFR — ${rule.section_id}`}
                code={rule.section_text}
                copyable
                maxHeight="22rem"
              />

              <div
                className="row gap-2 wrap"
                style={{ fontSize: "0.78rem" }}
              >
                <span className="muted">section_hash</span>
                <code
                  className="mono"
                  data-testid="section-hash"
                  style={{
                    wordBreak: "break-all",
                    background: "hsl(var(--surface-2))",
                    borderRadius: "0.3rem",
                    padding: "0.1rem 0.4rem",
                  }}
                >
                  {rule.section_hash}
                </code>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
