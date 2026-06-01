# Research synthesis — 2026-06-01

Inputs: three Perplexity **Sonar Deep Research** streams (raw responses in this
directory) plus a frontier-model **triangulation** (GPT-5.5, Gemini 3.1 Pro,
Grok 4.3, asked the same questions independently). This synthesis informed the
v0.2 design (Title IV, risk-tiering, golden corpus, provenance) and is recorded
here for traceability. Claims below are scoped to what the sources actually support.

## Triangulation convergence (3 independent frontier models)

Asked "what would make this policy-as-code POC genuinely credible to a technical
reviewer," all three converged on the same top additions, which v0.2 implements:

- A **golden scenario corpus** with expected `(outcome, citations, risk_tier,
  human_gate)` per fact pattern, CI-gated. → `tests/golden/`, `test_golden.py`.
- A **coverage / traceability matrix** (clause → quote → rule → scenarios) that
  shows gaps. → `regrails coverage report`, `docs/COVERAGE.md`.
- Explicit **`insufficient_facts` / `out_of_scope`** outcomes (real governance
  systems fail at "not enough information" and "not my job"). → added to the engine.
- A **pure decision path with no LLM**, provable by third parties. → `regrails decide`.
- **Hash-chained / tamper-evident** decision provenance. → `audit.py`, `audit verify`.

They also agreed on language to AVOID for a POC: "FERPA/Title IV compliant,"
"production-ready," "prevents violations," "legal advice," "zero hallucination."
The README's Limitations section adopts that hedging deliberately.

## Verified landscape + regulatory anchors (used in the encoding)

- **Policy-as-code + immutable audit trail + human-in-the-loop at critical
  decision points** is described as the strongest pattern for regulated,
  student-facing AI. OPA/Rego is called a *"particularly promising"* approach
  (not asserted as the dominant standard).
- **Documented equity failure:** IHEP / Dr. Denisa Gándara research finds
  predictive models more likely to falsely predict *failure* for Black and
  Latino students who actually succeed — "inequity often lives not in the
  algorithm but in how institutions deploy it." This is the harm RegRails'
  risk-tiering + human gate is designed to interrupt.
- **OCR, January 2025** — *"Avoiding the Discriminatory Use of Artificial
  Intelligence"* — recommends employees review/control AI output and intervene
  (human-in-the-loop) to avoid civil-rights violations.
- **FERPA "school official" exemption** for outsourced/AI vendors requires:
  performs an institutional function, under direct institutional control, and
  bound by use/redisclosure limits — encoded as `TIV`/`FERPA-99.31-A1B` safe-harbor.
- **Title IV / SAP (34 CFR 668.34)** — qualitative (GPA) + quantitative (pace) +
  150% max-timeframe + warning/probation/appeal — is a named policy-as-code
  target. Encoded in `data/encoded/title-iv-subset.yaml`.

## Factual cautions honored (NOT claimed anywhere in this repo or the application)

- The widely-cited "$9.4M OCR penalty" traces to **HIPAA/HHS-OCR**, not the
  Department of Education's OCR — not used.
- OPA/Rego is **not** claimed to be the dominant higher-ed policy-as-code tool.
- No relationship, pilot, or endorsement by Gates, Achieving the Dream, or any
  named institution is claimed. RegRails embodies the *pattern*; it is not *in* any program.

_Raw sources: `gates-dhss-strategy.json`, `edtech-ai-workflow-landscape.json`,
`ferpa-titleiv-policy-as-code.json` (full cited Sonar Deep Research responses)._
