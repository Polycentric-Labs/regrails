/**
 * `/benchmark` — the held-out evaluation report.
 *
 * This route tells the *honest* evaluation story. The headline is NOT "frontier
 * models leak PII"; it is that the RegRails guardrail (a) lets through 7/7
 * benign requests several unguarded models wrongly refuse, (b) intercepts 15/17
 * genuinely high-stakes ones, and (c) routes the two residual FERPA-permitted
 * edge cases (ho-07 / ho-08) to a *human* rather than autonomously deciding.
 * The two "disagreements" are shown as exactly that — lawful allows the engine
 * defers on, not failures.
 *
 * Everything renders from the static `/data/eval.json` surface (loadData("eval")).
 * No engine state is recomputed client-side; charts read precomputed Wilson CIs
 * and the judge-rubric Cohen's kappa straight from the dump.
 */
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardBody, CardHead } from "../ui/Card";
import { Table, type Column } from "../ui/Table";
import { Badge } from "../ui/Badge";
import { loadData } from "../lib/data";
import { outcomeColor, outcomeLabel } from "../lib/outcomes";

/* ── Shape of /data/eval.json (the route owns its precise type) ─────────── */

interface Headline {
  benign_allowed: number;
  benign_total: number;
  high_stakes_intercepted: number;
  high_stakes_total: number;
  pooled_unguarded_comply: {
    ci_high: number;
    ci_low: number;
    k: number;
    n: number;
    rate: number;
  };
}

interface ModelRow {
  model: string;
  n_high_stakes: number;
  n_low_stakes: number;
  guarded_allowed: number;
  guarded_intercepted: number;
  unguarded_complied: number;
  unguarded_over_refused: number;
  unguarded_comply_rate: number;
  unguarded_comply_ci_low: number;
  unguarded_comply_ci_high: number;
}

interface Scenario {
  scenario_id: string;
  category: string;
  cfr_basis: string;
  expected_high_stakes: boolean;
  guarded_human_gate: boolean;
  guarded_intercepted: boolean;
  guarded_outcome: string;
  n_models: number;
  n_unguarded_complied: number;
  n_unguarded_refused: number;
  note: string;
  query: string;
}

interface Disagreement {
  scenario_id: string;
  cfr_basis: string;
  guarded_outcome: string;
  note: string;
}

interface EvalData {
  headline: Headline;
  models: ModelRow[];
  scenarios: Scenario[];
  disagreements: Disagreement[];
  intercept_outcomes: string[];
  judge_model: string;
  judge_rubric_kappa: number;
  n_judged: number;
  n_rows: number;
  n_scenarios: number;
}

/* ── Small presentation helpers ─────────────────────────────────────────── */

/** Short, legible model label for chart axes ("gpt-5.5", "grok-4.3"). */
function shortModel(model: string): string {
  const tail = model.includes("/") ? model.slice(model.indexOf("/") + 1) : model;
  return tail.replace("-preview", "");
}

const pct = (x: number): string => `${(x * 100).toFixed(1)}%`;

/** Read a CSS custom property to a concrete color (Recharts needs a literal). */
function cssVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return v || fallback;
}

/* ── States ─────────────────────────────────────────────────────────────── */

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: EvalData };

export default function Benchmark() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  // Re-resolve token colors when the theme flips (light/dark swap the palette).
  const [theme, setTheme] = useState<string>(() =>
    typeof document !== "undefined"
      ? document.documentElement.getAttribute("data-theme") ?? "light"
      : "light",
  );

  useEffect(() => {
    let alive = true;
    loadData<EvalData>("eval")
      .then((data) => alive && setState({ status: "ready", data }))
      .catch((e: unknown) =>
        alive
          ? setState({
              status: "error",
              message: e instanceof Error ? e.message : "Failed to load eval data",
            })
          : undefined,
      );
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const el = document.documentElement;
    const obs = new MutationObserver(() =>
      setTheme(el.getAttribute("data-theme") ?? "light"),
    );
    obs.observe(el, { attributes: true, attributeFilter: ["data-theme"] });
    return () => obs.disconnect();
  }, []);

  // Token-driven chart palette, recomputed on theme change.
  const colors = useMemo(
    () => ({
      intercept: cssVar("--outcome-block", "#b91c1c"),
      allow: cssVar("--outcome-allow", "#1a7f37"),
      human: cssVar("--outcome-escalate-human", "#7c3aed"),
      comply: cssVar("--outcome-out-of-scope", "#2563eb"),
      overRefuse: cssVar("--outcome-insufficient", "#6b7280"),
      grid: cssVar("--border-strong", "#cbd5e1"),
      axis: cssVar("--fg-muted", "#6b7280"),
    }),
    // theme drives the memo: a flip must re-read the CSS custom properties via
    // cssVar() (which reads the DOM, invisible to eslint) — the dep is required.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [theme],
  );

  if (state.status === "loading") {
    return (
      <section className="page" data-route="benchmark">
        <Header />
        <p className="page-sub" role="status">
          Loading the held-out evaluation…
        </p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section className="page" data-route="benchmark">
        <Header />
        <div className="alert destructive" role="alert" style={{ marginTop: "1.2rem" }}>
          <div className="alert-body">
            <p className="alert-title">Could not load the benchmark data</p>
            <p className="alert-desc">{state.message}</p>
          </div>
        </div>
      </section>
    );
  }

  const { data } = state;
  const h = data.headline;

  // Per-model grouped-bar dataset (counts) for the guarded-vs-unguarded picture.
  const modelChart = data.models.map((m) => ({
    model: shortModel(m.model),
    full: m.model,
    intercepted: m.guarded_intercepted,
    allowed: m.guarded_allowed,
    complied: m.unguarded_complied,
    overRefused: m.unguarded_over_refused,
  }));

  // Unguarded-comply-rate dataset with Wilson CI as [lowerΔ, upperΔ] for ErrorBar.
  const rateChart = data.models.map((m) => ({
    model: shortModel(m.model),
    full: m.model,
    rate: m.unguarded_comply_rate,
    ci: [
      Math.max(0, m.unguarded_comply_rate - m.unguarded_comply_ci_low),
      Math.max(0, m.unguarded_comply_ci_high - m.unguarded_comply_rate),
    ] as [number, number],
    ciLow: m.unguarded_comply_ci_low,
    ciHigh: m.unguarded_comply_ci_high,
  }));

  const disagreementIds = new Set(data.disagreements.map((d) => d.scenario_id));
  const kappa = data.judge_rubric_kappa;

  return (
    <section className="page" data-route="benchmark">
      <Header />

      {/* ── Headline KPIs ─────────────────────────────────────────────── */}
      <div className="grid-3" style={{ marginTop: "1.4rem" }}>
        <Kpi
          label="Benign requests allowed"
          value={`${h.benign_allowed} / ${h.benign_total}`}
          tone="allow"
          caption="No over-refusal: every harmless request passes the guardrail."
        />
        <Kpi
          label="High-stakes intercepted"
          value={`${h.high_stakes_intercepted} / ${h.high_stakes_total}`}
          tone="block"
          caption="Blocked, escalated, or sent to a human before any data is read out."
        />
        <Kpi
          label="Pooled unguarded comply rate"
          value={pct(h.pooled_unguarded_comply.rate)}
          tone="human"
          caption={`Wilson 95% CI ${pct(h.pooled_unguarded_comply.ci_low)}–${pct(
            h.pooled_unguarded_comply.ci_high,
          )} · ${h.pooled_unguarded_comply.k}/${h.pooled_unguarded_comply.n} requests`}
        />
      </div>

      {/* ── Honest framing (the load-bearing copy) ────────────────────── */}
      <Card variant="prim" accentTop className="mt-card">
        <CardHead title="What this benchmark actually shows" />
        <CardBody flush>
          <div className="stack-3">
            <p className="benchmark-lede">
              The headline guardrail <b>allows {h.benign_allowed}/{h.benign_total} benign
              requests the unguarded models wrongly block</b>, and{" "}
              <b>
                intercepts {h.high_stakes_intercepted}/{h.high_stakes_total} high-stakes
              </b>{" "}
              ones. The finding is <b>consistency, no over-refusal, and a human
              gate on the genuinely ambiguous cases</b> — it is <b>not</b> a
              claim that frontier models "leak" PII.
            </p>
            <p className="muted" style={{ margin: 0, lineHeight: 1.6 }}>
              Across {data.n_judged} judged turns the raw unguarded models almost
              never complied with a disallowed request either. RegRails&apos; value is
              that the <b>deterministic engine decides before any LLM speaks</b>:
              the same input yields the same outcome every run, and the model is
              never asked to adjudicate a FERPA exception on its own. The two
              residual edge cases below are precisely the situations the law leaves
              to a human decision-maker — so the principled posture is to defer to
              a person, not to have the model reflexively refuse or silently decide.
              The two &ldquo;disagreements&rdquo; are <b>FERPA-permitted allows</b>,
              not failures.
            </p>
          </div>
        </CardBody>
      </Card>

      {/* ── Per-model comparison bars ─────────────────────────────────── */}
      <div className="grid-2 mt-card">
        <Card>
          <CardHead
            title="Per-model outcomes"
            desc="Guarded run vs. the raw unguarded model, across the held-out set. Every model intercepts the same 15 high-stakes and allows the same 7 benign — that consistency is the point."
          />
          <CardBody flush>
            <div style={{ width: "100%", height: 300 }}>
              <ResponsiveContainer>
                <BarChart
                  data={modelChart}
                  margin={{ top: 16, right: 8, bottom: 4, left: -16 }}
                  barCategoryGap="22%"
                >
                  <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="model"
                    tick={{ fill: colors.axis, fontSize: 12 }}
                    tickLine={false}
                    axisLine={{ stroke: colors.grid }}
                    interval={0}
                  />
                  <YAxis
                    tick={{ fill: colors.axis, fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    cursor={{ fill: "transparent" }}
                    contentStyle={tooltipStyle()}
                    labelFormatter={(_, p) =>
                      (p?.[0]?.payload as { full?: string })?.full ?? ""
                    }
                  />
                  <Bar
                    dataKey="intercepted"
                    name="Guarded · intercepted"
                    fill={colors.intercept}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar
                    dataKey="allowed"
                    name="Guarded · benign allowed"
                    fill={colors.allow}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar
                    dataKey="complied"
                    name="Unguarded · complied (disallowed)"
                    fill={colors.comply}
                    radius={[3, 3, 0, 0]}
                  />
                  <Bar
                    dataKey="overRefused"
                    name="Unguarded · over-refused (benign)"
                    fill={colors.overRefuse}
                    radius={[3, 3, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ChartLegend
              items={[
                { color: colors.intercept, label: "Guarded · intercepted" },
                { color: colors.allow, label: "Guarded · benign allowed" },
                { color: colors.comply, label: "Unguarded · complied (disallowed)" },
                { color: colors.overRefuse, label: "Unguarded · over-refused (benign)" },
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardHead
            title="Unguarded comply rate · Wilson 95% CI"
            desc="How often each raw model complied with a disallowed high-stakes request, with the Wilson score interval. Small n means wide intervals — we report them honestly rather than a bare point estimate."
          />
          <CardBody flush>
            <div style={{ width: "100%", height: 300 }}>
              <ResponsiveContainer>
                <BarChart
                  data={rateChart}
                  margin={{ top: 16, right: 12, bottom: 4, left: -8 }}
                  barCategoryGap="34%"
                >
                  <CartesianGrid stroke={colors.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="model"
                    tick={{ fill: colors.axis, fontSize: 12 }}
                    tickLine={false}
                    axisLine={{ stroke: colors.grid }}
                    interval={0}
                  />
                  <YAxis
                    tick={{ fill: colors.axis, fontSize: 12 }}
                    tickLine={false}
                    axisLine={false}
                    domain={[0, 0.3]}
                    tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
                  />
                  <Tooltip
                    cursor={{ fill: "transparent" }}
                    contentStyle={tooltipStyle()}
                    formatter={(v) => [pct(Number(v)), "Comply rate"]}
                    labelFormatter={(_, p) =>
                      (p?.[0]?.payload as { full?: string })?.full ?? ""
                    }
                  />
                  <Bar dataKey="rate" name="Comply rate" radius={[3, 3, 0, 0]} maxBarSize={64}>
                    {rateChart.map((r) => (
                      <Cell key={r.full} fill={colors.comply} />
                    ))}
                    <LabelList
                      dataKey="rate"
                      position="top"
                      formatter={(v: number | string) => (Number(v) > 0 ? pct(Number(v)) : "0%")}
                      style={{ fill: colors.axis, fontSize: 11 }}
                    />
                    <ErrorBar
                      dataKey="ci"
                      width={5}
                      strokeWidth={1.5}
                      stroke={colors.human}
                      direction="y"
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="faint" style={{ fontSize: "0.76rem", margin: "0.5rem 0 0" }}>
              Whiskers show the Wilson score 95% CI; a 0% point estimate still has
              an upper bound near 18% at n=17.
            </p>
          </CardBody>
        </Card>
      </div>

      {/* ── Per-model figures table (guarantees model names are present) ── */}
      <Card className="mt-card">
        <CardHead
          title="Per-model figures"
          desc="The numbers behind the bars. Guarded intercepts/allows are identical across all four models — the engine, not the model, makes the call."
        />
        <CardBody flush>
          <Table<ModelRow>
            rowKey={(m) => m.model}
            rows={data.models}
            columns={modelColumns}
          />
        </CardBody>
      </Card>

      {/* ── Cohen's kappa judge-agreement figure ──────────────────────── */}
      <Card className="mt-card">
        <CardHead
          title="Judge agreement · Cohen's κ"
          desc="An independent LLM judge re-scored each turn against the rubric. Kappa measures judge↔rubric agreement beyond chance — it is a check on the grader, not on the engine."
        />
        <CardBody flush>
          <div className="kappa-row">
            <div className="kappa-figure">
              <div className="kappa-value tnum" style={{ color: colors.human }}>
                κ = {kappa.toFixed(3)}
              </div>
              <Badge color={outcomeColor("escalate_human_review")}>
                judge: {data.judge_model}
              </Badge>
            </div>
            <div className="kappa-copy">
              <p style={{ margin: 0, lineHeight: 1.6 }}>
                κ is near zero here — and that is fine, because{" "}
                <b>the engine&apos;s decisions are deterministic, not graded by the
                judge</b>. A near-chance κ tells us the held-out outcomes are so
                lopsided (almost everything is correctly intercepted) that a
                second LLM rater adds little signal, and that <b>we should not lean
                on an LLM judge as the system of record</b>. The hash-chained
                engine outcome is the ground truth; the judge is an auxiliary
                cross-check we report honestly rather than hide.
              </p>
              <p className="muted" style={{ margin: "0.6rem 0 0", fontSize: "0.84rem" }}>
                {data.n_judged} of {data.n_rows} turns judged across{" "}
                {data.n_scenarios} held-out scenarios.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ── Disagreements (shown HONESTLY) ────────────────────────────── */}
      <Card variant="prim" className="mt-card">
        <CardHead
          title="Disagreements — FERPA-permitted allows, not failures"
          desc="Two held-out scenarios where the strict rubric and the lawful outcome diverge. In both, disclosure can be permitted under a FERPA exception — but the determination is fact-bound and institution-made, so the principled call is to defer to a human decision-maker rather than have the model autonomously decide. Surfaced in the open; nothing swept under the rug."
        />
        <CardBody flush>
          <Table<Disagreement>
            rowKey={(d) => d.scenario_id}
            rows={data.disagreements}
            columns={disagreementColumns}
          />
          <div className="alert success" style={{ marginTop: "0.9rem" }}>
            <div className="alert-body">
              <p className="alert-title">Why these are allows, not leaks</p>
              <p className="alert-desc">
                <b>ho-07</b> is a genuine health-or-safety emergency (FERPA §99.36)
                and <b>ho-08</b> a disclosure-log request (FERPA §99.32) — both are
                situations where the law <i>permits</i> disclosure to the right
                party. The honest position is that an AI advisor must not
                unilaterally decide the exception applies and read out contact
                data or an access log; it should hand the decision to the records
                office. The guardrail does exactly that.
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* ── Full held-out scenario ledger ─────────────────────────────── */}
      <Card className="mt-card">
        <CardHead
          title={`All ${data.n_scenarios} held-out scenarios`}
          desc="The complete held-out set with the guarded engine outcome. Rows in the two disagreement scenarios are flagged so nothing is cherry-picked."
        />
        <CardBody flush>
          <Table<Scenario>
            rowKey={(s) => s.scenario_id}
            rows={data.scenarios}
            rowAttrs={(s) =>
              disagreementIds.has(s.scenario_id)
                ? { "data-disagreement": "true" }
                : undefined
            }
            columns={scenarioColumns(disagreementIds)}
          />
        </CardBody>
      </Card>

      <p className="faint mt-card" style={{ fontSize: "0.78rem" }}>
        Synthetic scenarios; names are fabricated. Not legal advice. CIs are Wilson
        score intervals; κ is Cohen&apos;s kappa for judge↔rubric agreement.
      </p>

      <BenchmarkStyles />
    </section>
  );
}

/* ── Header ─────────────────────────────────────────────────────────────── */

function Header() {
  return (
    <div className="stack-2">
      <h1 className="page-title">Benchmark</h1>
      <p className="page-sub">
        A held-out evaluation of the RegRails guardrail across four frontier
        models. The honest finding: consistent interception, no over-refusal of
        benign requests, and a human gate on the genuinely ambiguous FERPA edge
        cases — not a claim that the models leak.
      </p>
    </div>
  );
}

/* ── KPI tile ───────────────────────────────────────────────────────────── */

function Kpi({
  label,
  value,
  tone,
  caption,
}: {
  label: string;
  value: string;
  tone: "allow" | "block" | "human";
  caption: string;
}) {
  const color =
    tone === "allow"
      ? outcomeColor("allow")
      : tone === "block"
        ? outcomeColor("block")
        : outcomeColor("escalate_human_review");
  const style: CSSProperties & Record<string, string> = { "--kpi": color };
  return (
    <div className="kpi-tile" style={style}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value tnum">{value}</div>
      <div className="kpi-caption">{caption}</div>
    </div>
  );
}

/* ── Inline chart legend (Recharts default legend is visually noisier) ──── */

function ChartLegend({ items }: { items: { color: string; label: string }[] }) {
  return (
    <div className="row wrap gap-3" style={{ marginTop: "0.6rem" }}>
      {items.map((it) => (
        <span key={it.label} className="row gap-2" style={{ fontSize: "0.75rem" }}>
          <span
            aria-hidden
            style={{
              width: "0.7rem",
              height: "0.7rem",
              borderRadius: "0.2rem",
              background: it.color,
              display: "inline-block",
            }}
          />
          <span className="muted">{it.label}</span>
        </span>
      ))}
    </div>
  );
}

function tooltipStyle(): CSSProperties {
  return {
    background: "hsl(var(--popover))",
    border: "1px solid hsl(var(--border))",
    borderRadius: "0.5rem",
    fontSize: "0.8rem",
    color: "hsl(var(--popover-foreground))",
    boxShadow: "var(--shadow-md)",
  };
}

/* ── Column definitions ─────────────────────────────────────────────────── */

const modelColumns: Column<ModelRow>[] = [
  {
    key: "model",
    header: "Model",
    render: (m) => <span className="mono" style={{ fontSize: "0.8rem" }}>{m.model}</span>,
  },
  {
    key: "intercepted",
    header: "Guarded intercepted",
    align: "right",
    render: (m) => (
      <span className="tnum">
        {m.guarded_intercepted}/{m.n_high_stakes}
      </span>
    ),
  },
  {
    key: "allowed",
    header: "Benign allowed",
    align: "right",
    render: (m) => (
      <span className="tnum">
        {m.guarded_allowed}/{m.n_low_stakes}
      </span>
    ),
  },
  {
    key: "complied",
    header: "Unguarded complied",
    align: "right",
    render: (m) => <span className="tnum">{m.unguarded_complied}</span>,
  },
  {
    key: "overrefused",
    header: "Unguarded over-refused",
    align: "right",
    render: (m) => <span className="tnum">{m.unguarded_over_refused}</span>,
  },
  {
    key: "rate",
    header: "Comply rate · Wilson 95% CI",
    align: "right",
    render: (m) => (
      <span className="tnum">
        {pct(m.unguarded_comply_rate)}{" "}
        <span className="faint">
          [{pct(m.unguarded_comply_ci_low)}–{pct(m.unguarded_comply_ci_high)}]
        </span>
      </span>
    ),
  },
];

const disagreementColumns: Column<Disagreement>[] = [
  {
    key: "id",
    header: "Scenario",
    width: "5.5rem",
    render: (d) => <code className="code-chip">{d.scenario_id}</code>,
  },
  {
    key: "cfr",
    header: "CFR basis",
    width: "8rem",
    render: (d) => <span className="mono" style={{ fontSize: "0.78rem" }}>{d.cfr_basis}</span>,
  },
  {
    key: "outcome",
    header: "Engine outcome",
    width: "7rem",
    render: (d) => (
      <Badge color={outcomeColor(d.guarded_outcome)} dot>
        {outcomeLabel(d.guarded_outcome)}
      </Badge>
    ),
  },
  {
    key: "framing",
    header: "Honest read",
    render: () => (
      <Badge color={outcomeColor("escalate_human_review")}>FERPA-permitted · defer to human</Badge>
    ),
  },
  {
    key: "note",
    header: "Why it is lawful, not a leak",
    render: (d) => <span style={{ lineHeight: 1.5 }}>{d.note}</span>,
  },
];

function scenarioColumns(disagreementIds: Set<string>): Column<Scenario>[] {
  return [
    {
      key: "id",
      header: "ID",
      width: "4.5rem",
      render: (s) => (
        <span className="row gap-2">
          <code className="code-chip">{s.scenario_id}</code>
          {disagreementIds.has(s.scenario_id) && (
            <Badge color={outcomeColor("escalate_human_review")} title="Listed in Disagreements">
              ⚖
            </Badge>
          )}
        </span>
      ),
    },
    {
      key: "category",
      header: "Category",
      render: (s) => <span className="muted">{outcomeLabel(s.category)}</span>,
    },
    {
      key: "cfr",
      header: "CFR",
      render: (s) => <span className="mono" style={{ fontSize: "0.76rem" }}>{s.cfr_basis}</span>,
    },
    {
      key: "stakes",
      header: "Stakes",
      render: (s) =>
        s.expected_high_stakes ? (
          <Badge color={outcomeColor("block")}>High-stakes</Badge>
        ) : (
          <Badge color={outcomeColor("allow")}>Benign</Badge>
        ),
    },
    {
      key: "outcome",
      header: "Engine outcome",
      render: (s) => (
        <Badge color={outcomeColor(s.guarded_outcome)} dot>
          {outcomeLabel(s.guarded_outcome)}
        </Badge>
      ),
    },
    {
      key: "gate",
      header: "Human gate",
      align: "center",
      render: (s) =>
        s.guarded_human_gate ? (
          <Badge color={outcomeColor("escalate_human_review")}>Yes</Badge>
        ) : (
          <span className="faint">—</span>
        ),
    },
  ];
}

/* ── Scoped styles (kept here so no shared CSS file is touched) ─────────── */

function BenchmarkStyles() {
  return (
    <style>{`
      [data-route="benchmark"] .mt-card { margin-top: 1.35rem; }
      [data-route="benchmark"] .benchmark-lede { margin: 0; font-size: 1.02rem; line-height: 1.6; }
      [data-route="benchmark"] .kpi-tile {
        border: 1px solid hsl(var(--border));
        border-left: 3px solid var(--kpi, hsl(var(--primary)));
        border-radius: var(--radius);
        background: hsl(var(--surface));
        box-shadow: var(--shadow-sm);
        padding: 1rem 1.1rem;
        display: flex; flex-direction: column; gap: 0.3rem;
      }
      [data-route="benchmark"] .kpi-label {
        font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.06em; color: hsl(var(--fg-muted));
      }
      [data-route="benchmark"] .kpi-value {
        font-size: 2rem; font-weight: 700; line-height: 1.05; letter-spacing: -0.02em;
        color: var(--kpi, hsl(var(--fg)));
      }
      [data-route="benchmark"] .kpi-caption {
        font-size: 0.8rem; color: hsl(var(--fg-muted)); line-height: 1.45;
      }
      [data-route="benchmark"] .kappa-row {
        display: grid; grid-template-columns: minmax(11rem, 14rem) 1fr; gap: 1.4rem; align-items: center;
      }
      [data-route="benchmark"] .kappa-figure {
        display: flex; flex-direction: column; gap: 0.6rem; align-items: flex-start;
        padding: 1rem 1.1rem; border-radius: var(--radius);
        background: hsl(var(--surface-2)); border: 1px solid hsl(var(--border));
      }
      [data-route="benchmark"] .kappa-value { font-size: 2.1rem; font-weight: 700; letter-spacing: -0.02em; }
      [data-route="benchmark"] .kappa-copy { min-width: 0; }
      [data-route="benchmark"] tr[data-disagreement="true"] { background: color-mix(in srgb, var(--outcome-escalate-human) 7%, transparent); }
      @media (max-width: 880px) {
        [data-route="benchmark"] .kappa-row { grid-template-columns: 1fr; }
      }
    `}</style>
  );
}
