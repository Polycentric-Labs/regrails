/**
 * `/mcp` — MCP Server. Documents the three agent-callable tools the RegRails
 * MCP server exposes (`consult_guardrail` / `list_rules` / `check_faithfulness`),
 * each with its real signature + return shape, a recorded agent transcript that
 * shows the consult-before-answer pattern, and the honest "runs locally over
 * stdio, not a hosted service" framing + install/run snippet.
 *
 * Source of truth for the signatures + return fields: src/regrails/mcp_server.py
 * (tool functions) and src/regrails/models.py (GuardrailDecision). The transcript
 * walks the real Title IV cascade: a student-in-default consult returns
 * outcome=escalate_human_review, risk_tier=high, human_gate_required=true cited to
 * 34 CFR § 668.32(g)(1) — so the agent refuses the eligibility answer and routes
 * to a human.
 *
 * Presentation-only: no network calls, no innerHTML. All payloads render through
 * <CodeBlock> (React children → textContent, XSS-safe).
 */
import Card, { CardBody, CardHead } from "../ui/Card";
import Badge from "../ui/Badge";
import CodeBlock from "../ui/CodeBlock";

interface ToolDoc {
  name: string;
  signature: string;
  summary: string;
  /** Label shown on the return badge (Python return annotation, condensed). */
  returnType: string;
  /** One-line description of the return shape. */
  returns: string;
}

const TOOLS: ToolDoc[] = [
  {
    name: "consult_guardrail",
    signature:
      "consult_guardrail(query, topic='unknown', requester_role='unknown', " +
      "purpose='unknown', data_requested=None, aid_determination_requested=False, " +
      "sap_status='unknown', student_in_default=None, consent_on_file=False, " +
      "student_opted_out_of_directory=False, emergency_justified=False, " +
      "safe_harbor_conditions_met=None)",
    summary:
      "The gate. Call this BEFORE answering any question about a student's " +
      "education records (FERPA) or financial-aid eligibility (Title IV). The " +
      "deterministic engine decides — no LLM is involved.",
    returnType: "dict",
    returns:
      "A GuardrailDecision as a dict — outcome, risk_tier, human_gate_required, " +
      "citations_emitted, matched_rules, framework, llm_response, latency_ms.",
  },
  {
    name: "list_rules",
    signature: "list_rules(framework='all')",
    summary:
      "Enumerate the encoded FERPA + Title IV rules so the agent can explain what " +
      "the guardrail covers. Filter by framework ('FERPA' / 'Title IV') or pass 'all'.",
    returnType: "list[dict]",
    returns:
      "A list of Rule dicts — id, framework, section_id, text, rule_type, " +
      "triggers, severity, citation, rationale.",
  },
  {
    name: "check_faithfulness",
    signature: "check_faithfulness()",
    summary:
      "Self-attest the encoding: verify every rule's source_quote is verbatim in " +
      "the bundled CFR text. Lets an agent prove provenance before it relies on a rule.",
    returnType: "dict",
    returns: 'A pass/total report — {"passed": int, "total": int}.',
  },
];

// Realistic recorded interaction. The agent receives a student question, emits a
// structured ConsultationRequest, CALLS consult_guardrail first, gets back
// escalate_human_review (Title IV loan-default bar, § 668.32(g)(1)), and only then
// answers — within the rails, declining the determination and routing to a human.
const TRANSCRIPT = `# Recorded MCP session — RegRails as a tool (stdio)
# Client: Claude Desktop · Server: regrails · transport: stdio
# The agent must consult the guardrail BEFORE answering. No LLM made the decision.

[student] "I defaulted on my student loan last year. Am I still eligible for
           financial aid this semester?"

[agent]   Recognizes a Title IV eligibility question → consults the guardrail
           before composing any answer.

→ tools/call  consult_guardrail
  {
    "query": "I defaulted on my loan last year — am I still eligible for aid?",
    "topic": "aid_status",
    "requester_role": "eligible_student",
    "purpose": "financial_aid",
    "aid_determination_requested": true,
    "student_in_default": true
  }

← result  (deterministic — engine decided, not the model)
  {
    "outcome": "escalate_human_review",
    "risk_tier": "high",
    "human_gate_required": true,
    "framework": "Title IV",
    "citations_emitted": ["34-CFR-668.32(g)(1)"],
    "matched_rules": ["TIV-668.32-G1"],
    "llm_response": "A student in default on a Title IV loan is not eligible for
      further Title IV aid under 34 CFR § 668.32(g)(1), absent a § 668.35
      exception. Do not confirm eligibility. Route the student to the
      financial-aid office to resolve the default (e.g. rehabilitation or
      consolidation) before any aid determination is made.",
    "latency_ms": 2
  }

[agent]   human_gate_required = true → MUST NOT issue a yes/no eligibility answer.
           Replies WITHIN the rails: explains the rule in general terms, declines
           the determination, and routes to a human.

[agent → student]
  "I can't make an eligibility determination on that — under 34 CFR § 668.32(g)(1)
   a borrower in default isn't eligible for further Title IV aid until the default
   is resolved, and that call is reserved for your financial-aid office. They can
   walk you through loan rehabilitation or consolidation to restore eligibility.
   Want me to point you to your school's financial-aid contact?"

# Without the gate, an ungated assistant might guess "yes" or "no". With it, the
# high-stakes, irreversible determination always lands with a human.`;

const INSTALL_SNIPPET = `# Install the package (ships the encoded FERPA + Title IV rules).
pip install regrails

# Run the MCP server over stdio. Two equivalent entry points:
regrails mcp serve     # CLI subcommand
regrails-mcp           # console-script entry point (pyproject [project.scripts])`;

const CLAUDE_CONFIG_SNIPPET = `// claude_desktop_config.json — wire RegRails in as a local stdio server.
{
  "mcpServers": {
    "regrails": {
      "command": "regrails-mcp"
    }
  }
}`;

function ToolCard({ tool }: { tool: ToolDoc }) {
  return (
    <Card accentTop hover>
      <CardHead>
        <div className="row-between wrap gap-2">
          <code className="mono" style={{ fontSize: "1rem", fontWeight: 600 }}>
            {tool.name}
          </code>
          <Badge color="hsl(var(--primary))" title="Return type">
            → {tool.returnType}
          </Badge>
        </div>
      </CardHead>
      <CardBody flush>
        <div className="stack-3">
          <p className="card-desc" style={{ margin: 0 }}>
            {tool.summary}
          </p>
          <CodeBlock code={tool.signature} language="python" label="Signature" />
          <div className="box dashed">
            <span
              className="muted"
              style={{
                fontSize: "0.68rem",
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              Returns
            </span>
            <p
              className="card-desc"
              style={{ margin: "0.3rem 0 0", lineHeight: 1.5 }}
            >
              {tool.returns}
            </p>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

export default function Mcp() {
  return (
    <section className="page" data-route="mcp">
      <h1 className="page-title">MCP Server</h1>
      <p className="page-sub">
        The guardrail as an agent-callable tool. An AI agent consults RegRails{" "}
        <em>before</em> it answers a question about a student&rsquo;s education
        records or financial aid — the deterministic engine decides, and the
        agent honors the outcome.
      </p>

      <div className="stack-6" style={{ marginTop: "1.6rem" }}>
        {/* Honest framing — not a hosted service. */}
        <div className="alert warning" role="note">
          <div className="alert-body">
            <p className="alert-title">Not a hosted live server</p>
            <p className="alert-desc">
              RegRails runs <strong>locally</strong> via{" "}
              <code className="code-chip">regrails mcp serve</code> (console
              entry point <code className="code-chip">regrails-mcp</code>) and
              speaks MCP over <strong>stdio</strong> — there is no public
              endpoint to call. You install the package and point your MCP client
              at the local process. The three tools below are what that process
              exposes.
            </p>
          </div>
        </div>

        {/* The three tools. */}
        <div className="stack-4">
          <div>
            <h2 className="h2-lg">Three tools</h2>
            <p className="page-sub" style={{ maxWidth: "70ch" }}>
              Signatures and return shapes are taken verbatim from the server
              module. <code className="code-chip">consult_guardrail</code> is the
              gate; the other two let an agent explain coverage and verify
              provenance.
            </p>
          </div>
          <div className="grid-3">
            {TOOLS.map((tool) => (
              <ToolCard key={tool.name} tool={tool} />
            ))}
          </div>
        </div>

        {/* Recorded transcript — the consult-before-answer pattern. */}
        <div className="stack-4">
          <div>
            <h2 className="h2-lg">Recorded transcript</h2>
            <p className="page-sub" style={{ maxWidth: "70ch" }}>
              A real interaction shape: the agent gets a student question, calls{" "}
              <code className="code-chip">consult_guardrail</code> first, receives
              a deterministic{" "}
              <Badge
                color="var(--outcome-escalate-human)"
                dot
                title="Outcome"
                className="cap"
              >
                escalate_human_review
              </Badge>{" "}
              decision with{" "}
              <Badge color="var(--risk-high)" dot title="Risk tier">
                high
              </Badge>{" "}
              risk and a mandatory human gate, and only then replies — within the
              rails.
            </p>
          </div>
          <Card variant="prim">
            <CardBody>
              <CodeBlock
                code={TRANSCRIPT}
                language="text"
                label="MCP session (stdio) — engine decided, not the model"
                copyable
                maxHeight="32rem"
              />
            </CardBody>
          </Card>
          <div className="alert" role="note">
            <div className="alert-body">
              <p className="alert-title">Why consult first?</p>
              <p className="alert-desc">
                The decision is 100% deterministic and made <em>before</em> any
                LLM call — the model never decides whether a disclosure is lawful.
                When{" "}
                <code className="code-chip">human_gate_required</code> is{" "}
                <code className="code-chip">true</code>, the outcome is reserved
                to a human (e.g. the financial-aid office); the agent declines the
                determination and routes it onward, rather than guessing.
              </p>
            </div>
          </div>
        </div>

        {/* Install + run. */}
        <div className="stack-4">
          <div>
            <h2 className="h2-lg">Install &amp; run</h2>
            <p className="page-sub" style={{ maxWidth: "70ch" }}>
              Install the package, then run the server locally and register it
              with your MCP client.
            </p>
          </div>
          <div className="grid-2">
            <Card>
              <CardHead title="Run the server" desc="Local stdio process." />
              <CardBody flush>
                <CodeBlock
                  code={INSTALL_SNIPPET}
                  language="bash"
                  label="shell"
                  copyable
                />
              </CardBody>
            </Card>
            <Card>
              <CardHead
                title="Register the client"
                desc="Point Claude Desktop (or any MCP client) at the local process."
              />
              <CardBody flush>
                <CodeBlock
                  code={CLAUDE_CONFIG_SNIPPET}
                  language="json"
                  label="claude_desktop_config.json"
                  copyable
                />
              </CardBody>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
}
