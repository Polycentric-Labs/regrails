/**
 * `/action` — GitHub Action. The composite action that gates an AI/automation
 * pipeline on the RegRails FERPA + Title IV guardrail: install `regrails` from
 * PyPI, run `regrails decide`, fail the job on a `block` / `escalate_human_review`
 * outcome, and emit a SARIF report into the GitHub Security tab.
 *
 * The two code panels below render the REAL action files verbatim
 * (`docs/action/action.yml` + `docs/action/workflow-example.yml`) so the page
 * never drifts from the shipped action. CodeBlock binds via React children →
 * textContent (no innerHTML), so the YAML cannot inject markup.
 */
import Badge from "../ui/Badge";
import Card, { CardBody, CardHead } from "../ui/Card";
import CodeBlock from "../ui/CodeBlock";
import { outcomeColor } from "../lib/outcomes";

/** Pinned tag the canonical usage references (matches action.yml's default + requirements.txt). */
const VERSION = "0.3.1";
const USES = `Polycentric-Labs/regrails/docs/action@v${VERSION}`;

/** The canonical one-line usage snippet. */
const USAGE_SNIPPET = `# .github/workflows/your-pipeline.yml
- name: RegRails gate
  uses: ${USES}
  with:
    query: \${{ inputs.user_query }}
    topic: "aid_status"
    extra-args: "--aid-determination --in-default"
`;

/**
 * Verbatim copy of docs/action/action.yml — the composite action definition.
 * Kept byte-for-byte in sync with the shipped file.
 */
const ACTION_YML = `name: "RegRails guardrail gate"
description: "Gate an AI/automation workflow on the RegRails FERPA + Title IV guardrail. Fails the job on block / escalate_human_review and writes a SARIF report."
author: "Allen Byrd"
branding:
  icon: "shield"
  color: "purple"

inputs:
  query:
    description: "The user-facing query the AI workflow is about to act on."
    required: true
  topic:
    description: "disclosure | aid_status | other | unknown"
    required: false
    default: "unknown"
  data:
    description: "Comma-separated data_requested items (e.g. 'gpa,transcript')."
    required: false
    default: ""
  extra-args:
    description: "Extra flags passed verbatim to \`regrails decide\` (e.g. '--aid-determination --in-default')."
    required: false
    default: ""
  fail-on:
    description: "Comma-separated outcomes that fail the job."
    required: false
    default: "block,escalate_human_review"
  version:
    description: "regrails version to install from PyPI."
    required: false
    default: "0.3.1"
  sarif-path:
    description: "Where to write the SARIF report."
    required: false
    default: "regrails.sarif"

outputs:
  outcome:
    description: "The GuardrailDecision outcome."
    value: \${{ steps.decide.outputs.outcome }}
  risk-tier:
    description: "The decision's risk tier."
    value: \${{ steps.decide.outputs.risk_tier }}

runs:
  using: composite
  steps:
    - name: Install regrails
      shell: bash
      env:
        RG_VERSION: \${{ inputs.version }}
      run: python -m pip install --quiet "regrails==\${RG_VERSION}"

    - name: Consult the guardrail
      id: decide
      shell: bash
      env:
        RG_QUERY: \${{ inputs.query }}
        RG_TOPIC: \${{ inputs.topic }}
        RG_DATA: \${{ inputs.data }}
        RG_EXTRA: \${{ inputs.extra-args }}
        RG_SARIF: \${{ inputs.sarif-path }}
      run: |
        regrails decide -q "$RG_QUERY" --topic "$RG_TOPIC" --data "$RG_DATA" $RG_EXTRA > rg_decision.json
        regrails decide -q "$RG_QUERY" --topic "$RG_TOPIC" --data "$RG_DATA" $RG_EXTRA --format sarif > "$RG_SARIF"
        outcome=$(python -c "import json;print(json.load(open('rg_decision.json'))['outcome'])")
        risk=$(python -c "import json;print(json.load(open('rg_decision.json'))['risk_tier'])")
        echo "outcome=$outcome" >> "$GITHUB_OUTPUT"
        echo "risk_tier=$risk" >> "$GITHUB_OUTPUT"
        echo "RegRails decision: outcome=$outcome risk=$risk"

    - name: Enforce the gate
      shell: bash
      env:
        RG_OUTCOME: \${{ steps.decide.outputs.outcome }}
        RG_FAILON: \${{ inputs.fail-on }}
      run: |
        IFS=',' read -ra failon <<< "$RG_FAILON"
        for o in "\${failon[@]}"; do
          if [ "$RG_OUTCOME" = "$o" ]; then
            echo "::error::RegRails gate: outcome '$RG_OUTCOME' is in fail-on list; failing the job."
            exit 1
          fi
        done
        echo "RegRails gate passed (outcome=$RG_OUTCOME)."
`;

/**
 * Verbatim copy of docs/action/workflow-example.yml — the drop-in caller
 * workflow. Kept byte-for-byte in sync with the shipped file.
 */
const WORKFLOW_YML = `# Example: gate an AI workflow on the RegRails guardrail in one \`uses:\` line.
# Copy this into .github/workflows/ in your own repo.
name: example — RegRails guardrail gate

on: [workflow_dispatch]

permissions:
  contents: read

jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # A high-stakes Title IV query: a student in loan default asking about
      # eligibility. RegRails returns escalate_human_review -> this FAILS the job,
      # so an automated "advisor" pipeline cannot ship the answer without a human.
      - name: RegRails gate
        uses: Polycentric-Labs/regrails/docs/action@v0.3.1
        with:
          query: "I defaulted on a loan a while back. Am I still eligible for aid this year?"
          topic: "aid_status"
          extra-args: "--aid-determination --in-default"

      # If the gate passes, upload the SARIF so it renders in code-scanning.
      - name: Upload SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: regrails.sarif
`;

/** What the composite action does, in order — the three runtime steps. */
const STEPS: { n: number; title: string; body: string }[] = [
  {
    n: 1,
    title: "Install regrails from PyPI",
    body: "Pins the published package (regrails==<version>) into the runner. No model, no API key, no network egress beyond PyPI — the engine is fully deterministic.",
  },
  {
    n: 2,
    title: "Run regrails decide",
    body: "Consults the guardrail on the pipeline's pending query and emits the typed GuardrailDecision (outcome + risk tier) as JSON, plus a SARIF 2.1.0 report.",
  },
  {
    n: 3,
    title: "Enforce the gate",
    body: "Fails the job when the outcome is in fail-on (default block, escalate_human_review). An automated 'advisor' cannot ship a high-stakes answer without a human.",
  },
];

/** The action.yml inputs, mirrored as a reference table. */
const INPUTS: {
  name: string;
  required: boolean;
  def: string;
  desc: string;
}[] = [
  { name: "query", required: true, def: "—", desc: "The user-facing query the AI workflow is about to act on." },
  { name: "topic", required: false, def: "unknown", desc: "disclosure · aid_status · other · unknown" },
  { name: "data", required: false, def: "(empty)", desc: "Comma-separated data_requested items (e.g. gpa,transcript)." },
  { name: "extra-args", required: false, def: "(empty)", desc: "Extra flags passed verbatim to regrails decide." },
  { name: "fail-on", required: false, def: "block,escalate_human_review", desc: "Comma-separated outcomes that fail the job." },
  { name: "version", required: false, def: VERSION, desc: "regrails version to install from PyPI." },
  { name: "sarif-path", required: false, def: "regrails.sarif", desc: "Where to write the SARIF report." },
];

/** The two outputs the action exposes to downstream steps. */
const OUTPUTS: { name: string; desc: string }[] = [
  { name: "outcome", desc: "The GuardrailDecision outcome (e.g. allow, block, escalate_human_review)." },
  { name: "risk-tier", desc: "The decision's risk tier (low · medium · high)." },
];

export default function Action() {
  return (
    <section className="page stack-6" data-route="action">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="stack-3">
        <div className="row gap-3 wrap">
          <h1 className="page-title">GitHub Action</h1>
          <Badge color={outcomeColor("escalate_human_review")} dot>
            composite action
          </Badge>
        </div>
        <p className="page-sub">
          Gate your AI pipeline on RegRails. One <code className="code-chip">uses:</code> line
          drops the deterministic FERPA + Title IV guardrail in front of an
          automated workflow — it installs <code className="code-chip">regrails</code> from
          PyPI, runs <code className="code-chip">regrails decide</code>, and fails the job the
          moment the engine returns <strong>block</strong> or{" "}
          <strong>escalate_human_review</strong>. No model in the loop; the engine
          decides before any LLM speaks.
        </p>
        <div className="row gap-2 wrap">
          <span className="code-chip">uses: {USES}</span>
          <Badge color={outcomeColor("allow")} dot>
            SARIF → Security tab
          </Badge>
          <Badge color={outcomeColor("out_of_scope")} dot>
            no API key
          </Badge>
        </div>
      </header>

      {/* ── What it does (3 steps) ─────────────────────────────────────── */}
      <div className="stack-3">
        <h2 className="h2">What it does</h2>
        <div className="grid-3">
          {STEPS.map((s) => (
            <Card key={s.n} accentTop>
              <CardHead
                title={
                  <span className="row gap-2">
                    <Badge color="var(--primary)" solid>
                      {s.n}
                    </Badge>
                    {s.title}
                  </span>
                }
                desc={s.body}
              />
            </Card>
          ))}
        </div>
        <div className="alert destructive">
          <div className="alert-body">
            <p className="alert-title">Fail-closed by default</p>
            <p className="alert-desc">
              The gate exits non-zero on any outcome in <code className="code-chip">fail-on</code>{" "}
              (<code className="code-chip">block</code>,{" "}
              <code className="code-chip">escalate_human_review</code>). A pipeline that
              would otherwise auto-send a high-stakes Title IV answer is stopped
              until a human reviews it — the SARIF report still uploads so the
              finding is visible in the repo's code-scanning view.
            </p>
          </div>
        </div>
      </div>

      {/* ── Canonical usage ────────────────────────────────────────────── */}
      <div className="stack-3">
        <h2 className="h2">Canonical usage</h2>
        <p className="muted" style={{ fontSize: "0.88rem", maxWidth: "70ch" }}>
          Add a single step to any workflow. Reference the action by its pinned
          tag — <code className="code-chip">@v{VERSION}</code> — and pass the query your
          pipeline is about to act on.
        </p>
        <CodeBlock
          code={USAGE_SNIPPET}
          language="yaml"
          label="Gate a pipeline step"
          copyable
        />
      </div>

      {/* ── Inputs + outputs ───────────────────────────────────────────── */}
      <div className="stack-3">
        <h2 className="h2">Inputs &amp; outputs</h2>
        <div className="grid-2">
          <Card>
            <CardHead title="Inputs" desc="Configure the gate per call site." />
            <CardBody flush>
              <div className="table-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Input</th>
                      <th>Required</th>
                      <th>Default</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {INPUTS.map((i) => (
                      <tr key={i.name}>
                        <td>
                          <code className="code-chip">{i.name}</code>
                        </td>
                        <td>
                          {i.required ? (
                            <Badge color={outcomeColor("block")}>required</Badge>
                          ) : (
                            <span className="faint">optional</span>
                          )}
                        </td>
                        <td className="mono" style={{ fontSize: "0.78rem" }}>
                          {i.def}
                        </td>
                        <td className="muted">{i.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHead
              title="Outputs"
              desc="Read these from a downstream step via steps.<id>.outputs.*."
            />
            <CardBody flush>
              <div className="table-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Output</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {OUTPUTS.map((o) => (
                      <tr key={o.name}>
                        <td>
                          <code className="code-chip">{o.name}</code>
                        </td>
                        <td className="muted">{o.desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>

      {/* ── The real action.yml ────────────────────────────────────────── */}
      <div className="stack-3">
        <h2 className="h2">
          The composite action — <code className="code-chip">action.yml</code>
        </h2>
        <p className="muted" style={{ fontSize: "0.88rem", maxWidth: "70ch" }}>
          The shipped definition, verbatim. Three composite steps: install,
          decide, enforce. Inputs are passed to{" "}
          <code className="code-chip">regrails decide</code> via environment
          variables (never interpolated into the shell), and{" "}
          <code className="code-chip">fail-on</code> drives the exit code.
        </p>
        <CodeBlock
          code={ACTION_YML}
          language="yaml"
          label="docs/action/action.yml"
          copyable
          downloadName="action.yml"
          maxHeight="32rem"
        />
      </div>

      {/* ── The real workflow-example.yml ──────────────────────────────── */}
      <div className="stack-3">
        <h2 className="h2">
          Drop-in workflow — <code className="code-chip">workflow-example.yml</code>
        </h2>
        <p className="muted" style={{ fontSize: "0.88rem", maxWidth: "70ch" }}>
          Copy this into <code className="code-chip">.github/workflows/</code> in your
          own repo. It gates a high-stakes Title IV query (a student in loan
          default asking about eligibility): RegRails returns{" "}
          <strong>escalate_human_review</strong>, which fails the job, then the
          SARIF uploads so the finding renders in code-scanning.
        </p>
        <CodeBlock
          code={WORKFLOW_YML}
          language="yaml"
          label="docs/action/workflow-example.yml"
          copyable
          downloadName="workflow-example.yml"
          maxHeight="32rem"
        />
        <div className="box">
          <p className="muted" style={{ fontSize: "0.82rem", margin: 0 }}>
            Synthetic data only. The engine is deterministic and offline — it
            needs no secrets, no environment variables, and no LLM. Pin the
            action to a tag (<code className="code-chip">@v{VERSION}</code>) so CI is
            reproducible.
          </p>
        </div>
      </div>
    </section>
  );
}
