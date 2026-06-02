/**
 * `/about` — About. Frames the deterministic-guardrail thesis, maps the work to
 * the role (the AI-automates-vs-human boundary written as code; auditability;
 * AI-in-the-loop governance), links the public artifacts (repo / PyPI / eval
 * dataset / Evidentia), and carries the AI-assistance note.
 *
 * Static content — no engine state is fetched here (the README + spec own this
 * copy). All external links open in a new tab with rel="noreferrer noopener".
 * No innerHTML anywhere; every value is a text node.
 */
import type { ReactNode } from "react";
import { Card, CardBody, CardHead } from "../ui/Card";
import { Badge } from "../ui/Badge";
import { CodeBlock } from "../ui/CodeBlock";
import { Table, type Column } from "../ui/Table";

/* ── External destinations (single source for this route) ─────────────── */
const LINKS = {
  repo: "https://github.com/Polycentric-Labs/regrails",
  pypi: "https://pypi.org/project/regrails/",
  evalDataset: "https://huggingface.co/datasets/Polycentric-Labs/regrails-eval",
  evidentia: "https://github.com/Polycentric-Labs/evidentia",
} as const;

interface ResourceLink {
  href: string;
  label: string;
  host: string;
  desc: string;
}

const RESOURCES: ResourceLink[] = [
  {
    href: LINKS.repo,
    label: "Source — Polycentric-Labs/regrails",
    host: "github.com",
    desc: "Apache-2.0. The engine, the 37 encoded rules, the golden corpus, the demo.",
  },
  {
    href: LINKS.pypi,
    label: "PyPI — regrails",
    host: "pypi.org",
    desc: "pip install regrails. Signed releases (PEP 740 + SLSA attestations).",
  },
  {
    href: LINKS.evalDataset,
    label: "Eval dataset — regrails-eval",
    host: "huggingface.co",
    desc: "The 24-scenario held-out benchmark corpus and published results.",
  },
  {
    href: LINKS.evidentia,
    label: "Evidentia — Polycentric-Labs/evidentia",
    host: "github.com",
    desc: "The open-source GRC platform whose patterns RegRails reuses.",
  },
];

/* ── Risk-tier model (the automate-vs-human boundary) ─────────────────── */
interface Tier {
  label: string;
  color: string;
  reversibility: string;
  disposition: string;
  example: string;
}

const TIERS: Tier[] = [
  {
    label: "Low",
    color: "var(--risk-low)",
    reversibility: "Reversible",
    disposition: "Safe to automate",
    example: "Explaining a rule; an out-of-scope question.",
  },
  {
    label: "Medium",
    color: "var(--risk-medium)",
    reversibility: "Bounded",
    disposition: "Automate with a cited obligation",
    example: "Consent required; a directory opt-out check.",
  },
  {
    label: "High",
    color: "var(--risk-high)",
    reversibility: "Irreversible",
    disposition: "Mandatory human gate",
    example: "Loan default; a failed-SAP aid-eligibility call.",
  },
];

/* ── Role mapping (JD ask ↔ what RegRails shows) ──────────────────────── */
interface RoleRow {
  ask: string;
  shows: ReactNode;
}

const ROLE_ROWS: RoleRow[] = [
  {
    ask: "The boundary between what AI can automate and what requires human judgment",
    shows: (
      <>
        The <strong>risk-tier + human-gate</strong> model — written as code.
        Reversible questions are automated; irreversible ones (loan default, a
        failed-SAP aid call) route to a human. The engine refuses to let the AI
        make the high-stakes call.
      </>
    ),
  },
  {
    ask: "Auditability",
    shows: (
      <>
        A hash-chained decision log; <code className="code-chip">audit verify</code>{" "}
        recomputes the chain and detects any edit, insertion, or deletion. Every
        decision carries its outcome, risk tier, gate flag, and citations.
      </>
    ),
  },
  {
    ask: "AI-in-the-loop governance",
    shows: (
      <>
        The LLM is a <strong>renderer, not a decider</strong>. The deterministic
        engine decides — with citations — before any model is called; the model
        only phrases the user-facing reply.
      </>
    ),
  },
  {
    ask: "Codify institutional policy into machine-readable logic, aligned to regulatory requirements (FERPA, Title IV)",
    shows: (
      <>
        37 machine-readable rules across <strong>FERPA</strong> and{" "}
        <strong>Title IV</strong>, each pinned verbatim to its CFR source text by
        a faithfulness gate.
      </>
    ),
  },
  {
    ask: "AI public goods",
    shows: (
      <>
        Apache-2.0, runs offline, no license cost — built so a lower-resourced
        institution can run it as-is.
      </>
    ),
  },
];

const ROLE_COLUMNS: Column<RoleRow>[] = [
  {
    key: "ask",
    header: "What the role asks for",
    width: "40%",
    render: (r) => <span className="muted">{r.ask}</span>,
  },
  {
    key: "shows",
    header: "What RegRails shows",
    render: (r) => r.shows,
  },
];

/* The deterministic-boundary proof — the engine runs with no LLM at all. */
const ENGINE_SNIPPET = `$ regrails decide \\
    --query "I defaulted on a loan; am I eligible for aid?" \\
    --topic aid_status --aid-determination --in-default

{ "outcome": "escalate_human_review",
  "risk_tier": "high",
  "human_gate_required": true,
  "citations_emitted": ["34-CFR-668.32(g)(1)"] }`;

/** Anchor styled as a primary button. Always opens in a new, isolated tab. */
function LinkButton({
  href,
  children,
  variant = "default",
}: {
  href: string;
  children: ReactNode;
  variant?: "default" | "outline";
}) {
  return (
    <a
      className={`btn ${variant}`}
      href={href}
      target="_blank"
      rel="noreferrer noopener"
    >
      {children}
    </a>
  );
}

export default function About() {
  return (
    <section className="page stack-6" data-route="about">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <header>
        <h1 className="page-title">About RegRails</h1>
        <p className="page-sub">
          A deterministic engine decides before any LLM speaks — so reversible
          questions are automated, irreversible ones go to a human, and every
          call leaves a tamper-evident record.
        </p>
      </header>

      {/* ── The thesis ─────────────────────────────────────────────── */}
      <Card accentTop>
        <CardHead
          title="The thesis"
          desc="Regulations are code — and the primitives to make them machine-readable, auditable, and AI-consultable already exist."
        />
        <CardBody flush>
          <div className="stack-3" style={{ fontSize: "0.92rem", lineHeight: 1.6 }}>
            <p style={{ margin: 0 }}>
              Federal regulation gets codified into machine-readable rules and
              wired into an AI advisor as a deny-by-default, risk-tiered
              guardrail. A <strong>deterministic engine</strong> consults those
              rules and emits a typed decision —{" "}
              <span className="mono">outcome</span>,{" "}
              <span className="mono">risk_tier</span>, and a{" "}
              <span className="mono">human_gate_required</span> flag —{" "}
              <strong>before any model is called</strong>. The LLM never makes
              the call; it only renders the reply.
            </p>
            <p style={{ margin: 0 }}>
              The split follows reversibility.{" "}
              <strong>Reversible questions are safe to automate.</strong>{" "}
              <strong>Irreversible ones</strong> — a loan default, a failed-SAP
              financial-aid eligibility call — <strong>route to a human</strong>,
              with citations attached. And because every decision can be appended
              to a hash-chained log, the record is tamper-evident: a single edit,
              insertion, or deletion breaks the chain.
            </p>
          </div>

          <div className="box dashed stack-3" style={{ marginTop: "1rem" }}>
            <div className="row wrap gap-2">
              {TIERS.map((t) => (
                <Badge key={t.label} color={t.color} dot>
                  {t.label} · {t.disposition}
                </Badge>
              ))}
            </div>
            <p className="muted" style={{ margin: 0, fontSize: "0.82rem" }}>
              The risk tier is derived from reversibility and blast radius. High
              and irreversible always means a mandatory human gate.
            </p>
          </div>
        </CardBody>
      </Card>

      {/* ── See the boundary directly ──────────────────────────────── */}
      <Card>
        <CardHead
          title="See the boundary, with no LLM at all"
          desc="Run the engine on its own. The decision is 100% deterministic and reproducible — no API key, no model."
        />
        <CardBody flush>
          <CodeBlock code={ENGINE_SNIPPET} label="The engine decides first" />
        </CardBody>
      </Card>

      {/* ── How this maps to the role ──────────────────────────────── */}
      <div className="stack-3">
        <div>
          <h2 className="h2-lg">How this maps to the role</h2>
          <p className="page-sub">
            Built for the Gates Foundation{" "}
            <em>Senior Program Officer, AI-Enabled Engagement Systems</em>{" "}
            charter. The mapping is deliberate.
          </p>
        </div>
        <Table
          columns={ROLE_COLUMNS}
          rows={ROLE_ROWS}
          rowKey={(r) => r.ask}
        />
      </div>

      {/* ── Links ──────────────────────────────────────────────────── */}
      <div className="stack-3">
        <div>
          <h2 className="h2-lg">Explore the artifacts</h2>
          <p className="page-sub">
            Everything is public and reproducible. Links open in a new tab.
          </p>
        </div>

        <div className="row wrap gap-2">
          <LinkButton href={LINKS.repo}>View on GitHub</LinkButton>
          <LinkButton href={LINKS.pypi} variant="outline">
            Install from PyPI
          </LinkButton>
          <LinkButton href={LINKS.evalDataset} variant="outline">
            Eval dataset
          </LinkButton>
        </div>

        <div className="grid-2">
          {RESOURCES.map((r) => (
            <Card key={r.href} hover>
              <CardBody>
                <div className="stack-2">
                  <div className="row-between gap-3">
                    <a
                      className="primary-link"
                      href={r.href}
                      target="_blank"
                      rel="noreferrer noopener"
                    >
                      {r.label}
                    </a>
                    <span className="code-chip">{r.host}</span>
                  </div>
                  <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
                    {r.desc}
                  </p>
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      </div>

      {/* ── Built by the author of Evidentia ───────────────────────── */}
      <Card>
        <CardHead title="Built by the author of Evidentia" />
        <CardBody flush>
          <p className="muted" style={{ margin: 0, fontSize: "0.9rem", lineHeight: 1.6 }}>
            By Allen Byrd, author of{" "}
            <a
              href={LINKS.evidentia}
              target="_blank"
              rel="noreferrer noopener"
            >
              Evidentia
            </a>
            , an open-source GRC platform with bundled framework catalogs,
            Sigstore-signed verifiable AI outputs, an MCP server, and
            supply-chain-attested releases. RegRails reuses its patterns
            directly: Pydantic models with{" "}
            <code className="code-chip">extra="forbid"</code>, a Jaccard
            verbatim-faithfulness gate, a string-valued{" "}
            <code className="code-chip">EventAction</code> audit enum, Typer CLI
            sub-commands, and env-file secret loading that never routes a key
            through tool context.
          </p>
        </CardBody>
      </Card>

      {/* ── Honest framing ─────────────────────────────────────────── */}
      <div className="alert warning" role="note">
        <div className="alert-body">
          <p className="alert-title">A proof-of-concept — not a compliance product</p>
          <p className="alert-desc">
            RegRails encodes selected provisions with verbatim traceability and
            routes high-stakes determinations to a human. It is not legal advice,
            does not certify compliance, and runs on synthetic data only. The
            faithfulness gate proves each quote matches the CFR text — not that
            the legal reading is correct; that needs an institutional FERPA /
            financial-aid officer.
          </p>
        </div>
      </div>

      {/* ── AI assistance ──────────────────────────────────────────── */}
      <Card>
        <CardHead title="AI assistance" />
        <CardBody flush>
          <p className="muted" style={{ margin: 0, fontSize: "0.85rem", lineHeight: 1.6 }}>
            This project was developed alongside AI platforms. Models used:
            Claude Opus 4.8, GPT-5.5, Gemini 3.1 Pro, Grok 4.3, DeepSeek,
            Perplexity Sonar (Deep Research + Pro). The encoded rules were
            grounded by committed research snapshots; every decision in the demo
            is made by the deterministic engine, not a model.
          </p>
        </CardBody>
      </Card>
    </section>
  );
}
