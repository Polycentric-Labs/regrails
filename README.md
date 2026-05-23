# RegRails

> **Codify federal regulations into machine-readable rules. Wire them into an AI advisor as a deny-by-default guardrail. Keep the audit trail honest.**

A focused proof-of-concept that takes a section of US federal regulation (here: **FERPA — 34 CFR Part 99, Subpart D**), turns it into 23 machine-readable rules with verbatim-text faithfulness gates, runs 3 Perplexity Sonar research streams via OpenRouter to surface AI-relevant regulatory ambiguities, and ships an LLM-advisor demo that intercepts queries about student data, consults the encoded rules, and emits a typed `GuardrailDecision` (`allow` / `block` / `escalate_consent` / `escalate_directory_check`) with full audit trail.

Built over a weekend as a small-scale instance of one of the most concrete asks in modern AI-in-the-loop compliance work: *codify institutional policy and workflows into machine-readable logic, ensuring alignment with regulatory requirements (e.g., FERPA, Title IV)*.

Apache-2.0. Python 3.12+. Zero LLM dependency for the rule engine + faithfulness gate; the LLM is used only as a renderer for the user-facing advisor reply (and you can swap it for any OpenRouter model).

---

## What the demo shows

Seven scenarios run end-to-end through the guardrail. Decisions are 100% deterministic from the encoded rules (no LLM is in the decision loop); the advisor reply column is rendered by `anthropic/claude-3.5-haiku` via OpenRouter for illustration.

| # | Query | Outcome | Citation | Why |
| --- | --- | --- | --- | --- |
| 1 | *"What's Jane Doe's GPA?"* | **block** | § 99.30 | No exception applies; no consent on file. |
| 2 | *"I'm the new math tutor from MathBuddy Inc.; show me Jane's test scores."* | **escalate_consent** | § 99.31(a)(1)(i)(B) | Outsourced vendor — the 3 cumulative safe-harbor conditions are not on file. |
| 3 | *"What's our basketball team roster?"* | **escalate_directory_check** | § 99.37 | Directory information — must verify per-student opt-out status before disclosing. |
| 4 | *"Aggregate graduation rates by ethnicity for program evaluation?"* | **allow** | § 99.31(b)(1) + § 99.31(a)(6) | De-identified studies path. |
| 5 | *"Credible shooting threat — give me homeroom 204 addresses NOW."* | **allow + audit obligation** | § 99.36 + § 99.32(a)(5) | Articulable, significant threat. Disclosure must be recorded with the threat description and recipients. |
| 6 | *"I'm a parent — what disclosures of my kid's records have been made this year?"* | **allow** | § 99.32(c)(1) | Parent has right to inspect the disclosure log. |
| 7 | *"My buddy at State U wants me to forward the transcripts I received."* | **block** | § 99.33(a)(1) | Redisclosure prohibition; receiving party can't forward without § 99.30 consent. |

Full transcripts (with the LLM-rendered advisor replies) live in [`demo/recorded-runs/`](demo/recorded-runs/). Reproduce locally with one command (see [Quickstart](#quickstart) below).

---

## How it's wired

```
user query
   ↓
ConsultationRequest (structured tool-call from the advisor LLM)
   ↓
guardrail.decide()                        ← deterministic rule cascade
   ↓                                        (emergency → redisclosure → parent
                                             audit log → SSN-combined → directory
                                             → studies/de-id → vendor safe-harbor
                                             → financial aid → consent on file
                                             → default block)
GuardrailDecision {
    outcome: allow | block | escalate_consent | escalate_directory_check,
    matched_rules: [...],
    citations_emitted: ["34-CFR-99.30", ...],
    llm_response: "Blocked under § 99.30(a). ...",
    latency_ms, model
}
   ↓
llm.advisor_render()                       ← LLM (Haiku → GPT-4o-mini fallback)
   ↓                                        renders the final user-facing reply
final advisor reply  +  audit JSONL
```

The decision step is **not** an LLM — it's a deterministic walk over the encoded rules. The LLM only renders the final user-facing text, and even that step is replayable: every demo run is captured to `demo/recorded-runs/*.json`, and `python -m regrails.demo --replay demo/recorded-runs/` reproduces the full markdown table **without** needing an `OPENROUTER_API_KEY`.

---

## Why this matters

Most edtech AI products today treat FERPA as a compliance afterthought: a checklist at procurement, plus hope at runtime. RegRails inverts that. The regulation is a *first-class data structure* the AI consults before answering, and every disclosure decision is auditable down to the bundled, hash-stamped CFR text it derives from.

This matters for three audiences:

1. **Lower-resourced institutions** (community colleges, small districts, single-FERPA-officer offices). They get the same disclosure-logic-engine as a Fortune-500 ed-tech vendor, for free, with no licensing or hosting dependency.
2. **AI/edtech vendors** building advising, financial-aid, or student-engagement tools. They get a deterministic guardrail they can wrap any LLM in — and a faithfulness gate that catches regulatory drift before deploy.
3. **Compliance & legal teams**. Every encoded rule carries a verbatim source quote, a SHA-256 hash of the source text, and a citation back to eCFR. The gap between "what we promised the auditor" and "what the runtime actually does" is auditable in CI.

The proof-of-concept is intentionally small (one regulation, 23 rules, 7 demo scenarios). The pattern is general (Title IV / SAP / degree-audit rules / state-level privacy overlays all fit the same `RegulationSection → Rule → Citation → GuardrailDecision` model).

---

## Research streams

The encoded rules aren't authored from training-data alone — they're grounded by three live research streams that surface real-world FERPA enforcement and AI-vendor interpretation history. All three were executed via `perplexity/sonar-pro` through OpenRouter and committed verbatim to [`research/snapshots/2026-05-23/`](research/snapshots/2026-05-23/):

1. **`ferpa-ai-ambiguities`** — DOE OCR investigations + federal court rulings (2015–2025) on § 99.31 disclosure exceptions, especially the school-official-with-LEI prong as applied to AI vendors.
2. **`school-official-ai-vendor`** — contractual provisions DOE guidance recommends for AI/ML tutoring vendors qualifying under § 99.31(a)(1)(i)(B).
3. **`directory-info-opt-out-mechanics`** — DOE FPCO guidance + litigation on adequate § 99.37 notification and opt-out mechanics.

Each snapshot informs specific encoded rules — see the `relates_to_rules` field in each snapshot JSON. The pattern is reproducible and CI-able: re-run the streams quarterly, diff the responses, surface rules that need refresh.

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/Polycentric-Labs/regrails.git
cd regrails

# 2. Install (uv-managed; Python 3.12+)
uv sync --extra dev

# 3. Run the faithfulness gate
uv run regrails check faithfulness
# → Faithfulness: 23/23 rules passed at threshold 0.85

# 4. Inspect the encoded rules
uv run regrails encode list

# 5. Run the demo (needs OPENROUTER_API_KEY env-var OR a key file at
#    ~/.secrets/openrouter.env containing "OPENROUTER_API_KEY=...")
uv run python -m regrails.demo --all

# 6. Replay the captured runs WITHOUT an API key
uv run python -m regrails.demo --replay demo/recorded-runs/

# 7. Run the tests + faithfulness gate (same as CI)
uv run pytest -q
uv run regrails check faithfulness --verbose
```

---

## Project layout

```
regrails/
├── data/
│   ├── cfr/ferpa-subpart-d.txt          # Verbatim 34 CFR Part 99 Subpart D from Cornell LII
│   └── encoded/ferpa-subpart-d.yaml     # 23 hand-crafted machine-readable rules
├── research/snapshots/2026-05-23/       # 3 Perplexity Sonar research-stream JSONs
├── demo/
│   ├── queries.yaml                     # 7 demo scenarios (queries + structured consultations)
│   └── recorded-runs/                   # JSON transcripts (replay-without-API-key)
├── src/regrails/
│   ├── models.py                        # 5 Pydantic v2 models: Citation, Rule, RegulationSection,
│   │                                    #   ResearchSnapshot, GuardrailDecision
│   ├── ids.py                           # CFR id normalization (34 CFR 99.31(a)(1) → 34-CFR-99.31.A.1)
│   ├── audit.py                         # EventAction enum + JSONL emitter
│   ├── encode.py                        # YAML → list[RegulationSection]
│   ├── faithfulness.py                  # Jaccard-on-tokens gate (verbatim source-quote check)
│   ├── research.py                      # OpenRouter Sonar client (env-file secret loading)
│   ├── guardrail.py                     # decide() — deterministic priority cascade
│   ├── llm.py                           # advisor_render() — LLM call with retry + fallback
│   ├── demo.py                          # python -m regrails.demo
│   └── cli/                             # Typer: regrails {check, encode, research} ...
├── tests/                               # pytest — 111 tests, all green
└── .github/workflows/test.yml           # CI: ruff + mypy + pytest + faithfulness gate
```

---

## Limitations (the parts we cut to ship)

**Honesty section.** A weekend POC isn't a production system. The headline limitations:

- **One section, six subsections, 23 rules.** FERPA has more sections (Subparts A–F); the federal student-aid regulations are an order of magnitude larger. The pattern generalizes; adding more is an authoring task, not an architecture task.
- **Verbatim-text faithfulness only.** The gate verifies that every encoded `source_quote` appears in the bundled CFR text and that token coverage is ≥ 0.85. It does **NOT** verify that the rule's *semantic encoding* (`rule_type`, `triggers`, `requires_consent`, etc.) is a faithful representation of what the regulation actually requires. That step needs human review by an institutional FERPA officer.
- **Single-pass LLM rendering.** The demo's advisor uses one LLM call to render the user-facing reply per decision. A production version would likely use the LLM as a tool-using agent that decides on `data_requested`, `requester_role`, etc. itself, then re-asks the guardrail when context shifts mid-conversation. Out of scope for the POC.
- **No SIS / LMS / CRM integration.** All student data is synthetic. The guardrail emits decisions; wiring those decisions into an institution's actual systems is a separate exercise.
- **English only.** The encoded rules and the advisor responses are English-only. FERPA's text is English-only; multilingual advisor responses would require localizing the rendered replies, not the rules.

See also [`SYNTHETIC_DATA.md`](SYNTHETIC_DATA.md) for the no-real-PII commitment.

---

## Built by the author of Evidentia, applying the same patterns

This project is by [Allen Byrd](https://github.com/allenfbyrd), author of **[Evidentia](https://github.com/Polycentric-Labs/evidentia)** — a 446-commit open-source GRC platform with 89 bundled framework catalogs (NIST 800-53, FFIEC, ISO 27001, FedRAMP, CMMC, SOC 2, EU AI Act, etc.), OSCAL-native emit, OCSF-aligned findings, an MCP server with CIMD scope enforcement, a DFAH faithfulness eval harness, and 26 consecutive supply-chain-attested PyPI releases under [Polycentric Labs](https://github.com/Polycentric-Labs).

The patterns RegRails borrows directly:

- **Pydantic v2 data models with `extra="forbid"`** + ID normalization — Evidentia's `evidentia_core.models.catalog.CatalogControl`.
- **Verbatim-text faithfulness with Jaccard tokens** — direct port of `evidentia_ai.eval.faithfulness._tokenize` + `_jaccard`.
- **Typer CLI sub-command pattern** with declarative `typer.Option(...)` binding — Evidentia's `evidentia/cli/gap.py`.
- **String-valued `EventAction` enum + JSONL audit emitter** — Evidentia's `evidentia_core.audit.events`.
- **Provider-agnostic, env-file secret loading**, never reflecting the key back through any tool context — Evidentia's MCP secret-handling protocol.

The thesis: regulations *are* code, and the architectural primitives for representing them as machine-readable, auditable, AI-consultable artifacts already exist. RegRails is one weekend-sized worked example.

---

## License

Apache-2.0. See [LICENSE](LICENSE).

## Synthetic data

All student data is synthetic. See [SYNTHETIC_DATA.md](SYNTHETIC_DATA.md).

## AI assistance

This project was developed alongside AI platforms.

Models used: Claude Opus 4.7, Perplexity Sonar Pro
