/**
 * `/coverage` — Coverage. The credibility story: we SHOW what isn't covered.
 *
 * Renders the static `data/coverage.json` surface (dumped from the installed
 * regrails package by scripts/gen_web_data.py — never recomputed client-side):
 *   - a headline "31 / 37 rules covered" stat strip,
 *   - a per-framework matrix of every rule → its golden-scenario count, with
 *     covered vs. not-covered called out visually, and
 *   - a prominent "Known gaps (6)" section, one card per uncovered rule with
 *     its rule ID + the verbatim rationale from the data.
 *
 * Presentation only: outcomes/risk colors come from lib/outcomes; all data
 * binds via React children (text nodes) — no innerHTML, untrusted strings can
 * never inject markup.
 */
import { useEffect, useMemo, useState } from "react";
import { Badge } from "../ui/Badge";
import { Card, CardBody, CardHead } from "../ui/Card";
import { Table, type Column } from "../ui/Table";
import { loadData, DataLoadError } from "../lib/data";
import { riskColor } from "../lib/outcomes";

/* ── Shape of data/coverage.json (the route owns its precise type) ─────── */

interface MatrixRule {
  framework: string;
  rule_id: string;
  section: string;
  risk_tier: string;
  n_scenarios: number;
  scenarios: string[];
}

interface Gap {
  framework: string;
  rule_id: string;
  section: string;
  rationale: string;
}

interface CoverageData {
  n_covered: number;
  n_rules: number;
  n_gaps: number;
  n_golden_scenarios: number;
  matrix: MatrixRule[];
  gaps: Gap[];
}

/** A rule is covered iff at least one golden scenario exercises it. */
const isCovered = (rule: MatrixRule): boolean => rule.n_scenarios > 0;

/* ── Small presentational helpers ─────────────────────────────────────── */

function StatTile({
  value,
  label,
  sub,
  tone,
}: {
  value: string;
  label: string;
  sub?: string;
  tone?: "default" | "dest";
}) {
  return (
    <div className="box" style={{ padding: "0.95rem 1.05rem" }}>
      <div
        className="tnum"
        style={{
          fontSize: "2rem",
          fontWeight: 700,
          lineHeight: 1.05,
          letterSpacing: "-0.02em",
          color:
            tone === "dest"
              ? "hsl(var(--destructive))"
              : "hsl(var(--foreground))",
        }}
      >
        {value}
      </div>
      <div
        style={{ fontSize: "0.82rem", fontWeight: 600, marginTop: "0.2rem" }}
      >
        {label}
      </div>
      {sub && (
        <div className="muted" style={{ fontSize: "0.76rem", marginTop: "0.1rem" }}>
          {sub}
        </div>
      )}
    </div>
  );
}

/** Thin covered/not pip used in the matrix status column. */
function StatusPip({ covered }: { covered: boolean }) {
  const color = covered ? "var(--outcome-allow)" : "var(--outcome-block)";
  return (
    <Badge color={color} dot>
      {covered ? "Covered" : "Not covered"}
    </Badge>
  );
}

/* ── Loading / error states (mirror the ErrorBoundary's tone) ─────────── */

function LoadingState() {
  return (
    <section className="page" data-route="coverage" aria-busy="true">
      <h1 className="page-title">Coverage</h1>
      <p className="page-sub">Loading coverage matrix…</p>
    </section>
  );
}

function FailedState({ message }: { message: string }) {
  return (
    <section className="page" data-route="coverage">
      <h1 className="page-title">Coverage</h1>
      <div className="alert destructive" role="alert" style={{ marginTop: "1rem" }}>
        <div className="alert-body">
          <p className="alert-title">Couldn’t load coverage data</p>
          <p className="alert-desc">{message}</p>
        </div>
      </div>
    </section>
  );
}

/* ── Route ────────────────────────────────────────────────────────────── */

export default function Coverage() {
  const [data, setData] = useState<CoverageData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    loadData<CoverageData>("coverage")
      .then((d) => {
        if (live) setData(d);
      })
      .catch((e: unknown) => {
        if (!live) return;
        setError(
          e instanceof DataLoadError
            ? e.message
            : "Unexpected error reading /data/coverage.json.",
        );
      });
    return () => {
      live = false;
    };
  }, []);

  // Group the matrix by framework so each regulation gets its own panel, and
  // pre-sort uncovered rules to the top of each group (the honest framing:
  // surface the gaps, don't bury them).
  const grouped = useMemo(() => {
    if (!data) return [];
    const byFramework = new Map<string, MatrixRule[]>();
    for (const rule of data.matrix) {
      const list = byFramework.get(rule.framework) ?? [];
      list.push(rule);
      byFramework.set(rule.framework, list);
    }
    return [...byFramework.entries()].map(([framework, rules]) => {
      const sorted = [...rules].sort((a, b) => {
        // Uncovered first, then by rule id for a stable, scannable order.
        const ac = isCovered(a) ? 1 : 0;
        const bc = isCovered(b) ? 1 : 0;
        if (ac !== bc) return ac - bc;
        return a.rule_id.localeCompare(b.rule_id);
      });
      const covered = sorted.filter(isCovered).length;
      return { framework, rules: sorted, covered, total: sorted.length };
    });
  }, [data]);

  if (error) return <FailedState message={error} />;
  if (!data) return <LoadingState />;

  const pct = data.n_rules
    ? Math.round((data.n_covered / data.n_rules) * 100)
    : 0;

  const columns: Column<MatrixRule>[] = [
    {
      key: "rule",
      header: "Rule",
      render: (r) => <span className="mono">{r.rule_id}</span>,
    },
    {
      key: "section",
      header: "CFR section",
      render: (r) => <span className="code-chip">{r.section}</span>,
    },
    {
      key: "risk",
      header: "Risk",
      render: (r) =>
        r.risk_tier && r.risk_tier !== "-" ? (
          <Badge color={riskColor(r.risk_tier)} capitalize>
            {r.risk_tier}
          </Badge>
        ) : (
          <span className="faint">—</span>
        ),
    },
    {
      key: "scenarios",
      header: "Scenarios",
      align: "right",
      render: (r) => (
        <span className="tnum mono" title={r.scenarios.join(", ") || undefined}>
          {r.n_scenarios}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <StatusPip covered={isCovered(r)} />,
    },
  ];

  return (
    <section className="page stack-6" data-route="coverage">
      {/* Header */}
      <div className="stack-2">
        <h1 className="page-title">Coverage</h1>
        <p className="page-sub">
          Every rule in the policy pack, mapped to the golden scenarios that
          exercise it. We publish the gaps too — a rule with no scenario is
          shown as <b>not covered</b>, not hidden.
        </p>
      </div>

      {/* Headline stat strip */}
      <div className="stack-3">
        <div className="row gap-3 wrap" style={{ alignItems: "baseline" }}>
          <span
            className="tnum"
            style={{
              fontSize: "2.6rem",
              fontWeight: 700,
              letterSpacing: "-0.025em",
              lineHeight: 1,
            }}
          >
            {data.n_covered} / {data.n_rules}
          </span>
          <span style={{ fontSize: "1.05rem", fontWeight: 600 }}>
            rules covered
          </span>
          <Badge color="var(--outcome-allow)" dot>
            {pct}% coverage
          </Badge>
        </div>

        {/* Proportional coverage bar (covered vs. gap). */}
        <div
          aria-hidden="true"
          style={{
            display: "flex",
            height: "0.6rem",
            borderRadius: "999px",
            overflow: "hidden",
            border: "1px solid hsl(var(--border))",
            background: "hsl(var(--surface-2))",
          }}
        >
          <div
            style={{
              width: `${pct}%`,
              background: "var(--outcome-allow)",
            }}
          />
          <div
            style={{
              flex: 1,
              background: "var(--outcome-block)",
              opacity: 0.85,
            }}
          />
        </div>

        <div className="grid-3">
          <StatTile
            value={String(data.n_covered)}
            label="Rules covered"
            sub="≥ 1 golden scenario"
          />
          <StatTile
            value={String(data.n_gaps)}
            label="Known gaps"
            sub="documented, not hidden"
            tone="dest"
          />
          <StatTile
            value={String(data.n_golden_scenarios)}
            label="Golden scenarios"
            sub="hand-labeled fixtures"
          />
        </div>
      </div>

      {/* Coverage matrix — one panel per framework */}
      <div className="stack-4">
        <div className="stack-2">
          <h2 className="h2-lg">Coverage matrix</h2>
          <p className="muted" style={{ fontSize: "0.85rem", maxWidth: "62ch" }}>
            Each row is a single rule. The scenario count is the number of
            golden fixtures whose expected decision depends on that rule.
          </p>
        </div>

        {grouped.map((g) => (
          <Card key={g.framework} accentTop>
            <CardHead
              title={g.framework}
              desc={`${g.covered} of ${g.total} rules covered by at least one golden scenario.`}
            >
              <div className="row gap-2 wrap" style={{ marginTop: "0.25rem" }}>
                <Badge color="var(--outcome-allow)" dot>
                  {g.covered} covered
                </Badge>
                {g.total - g.covered > 0 && (
                  <Badge color="var(--outcome-block)" dot>
                    {g.total - g.covered} not covered
                  </Badge>
                )}
              </div>
            </CardHead>
            <CardBody flush>
              <Table
                columns={columns}
                rows={g.rules}
                rowKey={(r) => r.rule_id}
                rowAttrs={(r) => ({
                  "data-covered": String(isCovered(r)),
                })}
                empty="No rules in this framework."
              />
            </CardBody>
          </Card>
        ))}
      </div>

      {/* Known gaps — the credibility section */}
      <div className="stack-4">
        <div className="stack-2">
          <h2 className="h2-lg">Known gaps ({data.n_gaps})</h2>
          <p className="muted" style={{ fontSize: "0.85rem", maxWidth: "62ch" }}>
            These rules have no golden scenario yet. We list each one with the
            reason it’s uncovered so the evaluation set’s blind spots are on the
            record, not in the footnotes.
          </p>
        </div>

        <div className="grid-2" data-gap-list>
          {data.gaps.map((gap) => (
            // Card doesn't forward arbitrary DOM attrs, so the test hook
            // (data-gap-id) lives on a thin wrapper element.
            <div key={gap.rule_id} data-gap-id={gap.rule_id}>
              <Card variant="dest" hover>
                <CardBody>
                  <div className="stack-3">
                    <div className="row-between gap-2">
                      <span className="mono" style={{ fontWeight: 600 }}>
                        {gap.rule_id}
                      </span>
                      <Badge color="var(--outcome-block)" dot>
                        Not covered
                      </Badge>
                    </div>
                    <p
                      className="alert-desc"
                      style={{ margin: 0, color: "hsl(var(--foreground))" }}
                    >
                      {gap.rationale}
                    </p>
                    <div className="row gap-2 wrap">
                      <span className="code-chip">{gap.framework}</span>
                      <span className="code-chip">{gap.section}</span>
                    </div>
                  </div>
                </CardBody>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
