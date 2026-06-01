# RegRails — methodology, scope, and limits

This document states what RegRails does, what it does not do, and how every
claim in the repository can be re-derived from the committed files. It is written
to be checked, not believed. Where a number appears, it is the number the tooling
produces; the commands to reproduce each one are in [§8](#8-reproducibility).

RegRails is a proof-of-concept. It is not legal advice, not a compliance
certification, and not production software. Nothing here should be relied on to
make a real disclosure, eligibility, or aid decision about a real student.

## 1. What this is / is not

RegRails encodes *selected* provisions of two U.S. higher-education frameworks
into machine-readable rules and wires them into an AI advisor as a
deny-by-default, risk-tiered guardrail consulted before the model answers:

- **FERPA** — 34 CFR Part 99, Subpart D (education-record disclosure).
- **Title IV** — a subset of 34 CFR Part 668 (Satisfactory Academic Progress
  under § 668.34 and student eligibility under § 668.32).

It **is** a worked example of the policy-as-code pattern for AI-in-the-loop
governance: a deterministic decision engine, a verbatim-text faithfulness
check, a hash-chained decision log, and a published rule-to-scenario coverage
matrix.

It **is not** a statement that any institution using it is "compliant," a
substitute for review by a FERPA or financial-aid officer, or a system that
"prevents violations." It produces auditable guardrails and escalation paths.
Whether the encoded reading of a rule is *legally correct* is outside what the
tooling can establish (see [§5](#5-the-faithfulness-gate)).

## 2. Scope boundary

The encoding covers eight CFR sections. The table below is what is actually
present in `data/encoded/` — exhaustive, not illustrative.

| Framework | Encoded sections | Rules encoded |
| --- | --- | --- |
| FERPA (Part 99, Subpart D) | §§ 99.30, 99.31, 99.32, 99.33, 99.36, 99.37 | 23 |
| Title IV (Part 668, subset) | §§ 668.34 (SAP), 668.32 (eligibility) | 14 |
| **Total** | **8 sections** | **37** |

### In-scope CFR that is deliberately NOT encoded

The boundary matters more than the coverage, so it is stated explicitly:

- **FERPA § 99.31 disclosure exceptions** — § 99.31 has roughly a dozen
  no-consent exceptions; eight are encoded (the school-official prong with its
  outsourced-vendor sub-prong, plus the audit, financial-aid, studies,
  judicial-order, health/safety, and de-identification prongs). The remaining
  § 99.31(a) exceptions are not.
- **Sections referenced but not themselves encoded** — some rules name
  machinery that is not separately modeled: **§ 99.34** (disclosure to other
  educational agencies), **§ 99.35** (the audit conditions the § 99.31(a)(3)
  rule defers to), **§ 99.38** (juvenile-justice disclosures), and **§ 99.39**
  (definitions). A rule may cite these in its text without the engine enforcing
  their conditions.
- **Title IV** — only **§ 668.34** (SAP) and a **subset of § 668.32**
  (eligibility) are encoded, out of the whole of Part 668. Both source files are
  bundled subsets and say so in their headers (`data/cfr/title-iv-subset.txt`:
  "This is a SUBSET … it is not the complete Part 668"). § 668.35 (reinstatement
  of eligibility after default), which the default rules reference as the
  resolution path, is not encoded.

## 3. Label provenance

The golden corpus (`tests/golden/ferpa.jsonl`, `tests/golden/title_iv.jsonl`)
contains **22 labeled scenarios**: 12 FERPA, 10 Title IV (one of the Title IV
cases is an out-of-scope control). Each fixes the expected
`(outcome, risk_tier, human_gate, citations)` for a concrete fact pattern, and
each expected outcome is pinned to its controlling CFR citation in the
`expected_citations_contains` field — e.g. the loan-default scenario is labeled
`escalate_human_review / high / human_gate=true` citing `34-CFR-668.32(g)(1)`.
That citation is the provenance: it names the clause that justifies the label.

**Honest limitation on labeling:** these labels were authored by a single person
(the project author), reasoning from the regulatory text and the committed
research snapshots, without independent review by a FERPA or financial-aid
practitioner. They are one defensible reading of the cited clauses, not an
adjudicated ground truth; a second qualified reviewer could disagree with a
label, and that disagreement would be a legitimate finding, not a bug. The
golden corpus and the full v0.2 encoding were committed in
`b1c2796de9365ce8586f3a6eba1ed0e6258134c1`.

## 4. Coverage and gaps

`regrails coverage report` builds a rule→scenario traceability matrix from the
golden corpus and records it in [`COVERAGE.md`](COVERAGE.md). The numbers there:

> **37 encoded rules; 31 are exercised by at least one of 22 golden scenarios;
> the remaining 6 rules have no scenario yet.**

The six uncovered rules are listed, not hidden:

- `FERPA-99.30-3` (§ 99.30 — electronic-consent validity)
- `FERPA-99.31-A3` (§ 99.31 — audit/evaluation exception)
- `FERPA-99.31-A4` (§ 99.31 — financial-aid exception)
- `FERPA-99.31-A9` (§ 99.31 — judicial order / subpoena)
- `FERPA-99.33-A2` (§ 99.33 — purpose-limitation on received PII)
- `FERPA-99.36-B1` (§ 99.36 — disciplinary-action information in records)

These are gaps in *test coverage*, surfaced on purpose. A rule with no scenario
means the engine's behavior on it is unverified by any example, so its routing
should be treated as unproven until a scenario exists. A coverage matrix that
showed only the covered rules would overstate what has been checked.

## 5. The faithfulness gate

`regrails check faithfulness` ([`src/regrails/faithfulness.py`](../src/regrails/faithfulness.py))
verifies **verbatim text**, and only that. For each rule it checks the
`source_quote` against the bundled CFR text for the matching section. A rule
passes if the quote is a character-for-character substring of the bundled text
**OR** its token coverage (`|quote ∩ section| / |quote|`) is at least **0.85**.
With a hash over each bundled section, this gives a traceable chain from public
CFR text → bundle → encoded `source_quote`.

This guarantees the words attributed to a section are actually in that section,
so the encoding cannot silently paraphrase or fabricate regulatory text.

**What it does not guarantee** is that the *semantic* encoding is a correct
legal reading. The gate says nothing about whether the chosen `rule_type`, the
`triggers` that route a query to the rule, or the assigned `risk_tier` are
right. A rule could quote the statute perfectly and still map to the wrong
outcome. Establishing semantic correctness requires review by an institutional
FERPA or financial-aid officer; the faithfulness gate is a necessary check, not
a sufficient one.

## 6. Risk tiers and the human gate

Each decision carries a risk tier derived from reversibility and blast radius;
the tier drives a routing stance:

- **low / reversible** → may be automated (explaining a rule, an out-of-scope
  question, an aggregate de-identified release).
- **medium** → automate only with a cited obligation or a quick check (consent
  defect, directory opt-out state, recordkeeping duty).
- **high / irreversible** → **mandatory human gate.** Loss of aid eligibility,
  loan default, a yes/no eligibility determination — the engine refuses to let
  the AI answer and routes to a human (the financial-aid office). In the Title
  IV encoding, § 668.34(a)(7) (SAP termination) and § 668.32(g)(1) (default)
  carry the `high` tier and force the gate.

This is a **design stance, not a guarantee.** Tiers are assigned by the author
per rule; the engine enforces the stance deterministically, but it cannot
promise every high-stakes situation has been *classified* as high. A
miscategorized rule would route a serious case as medium. The gate is only as
good as the tiering, which is itself unreviewed (see [§3](#3-label-provenance)).

## 7. Known failure modes

Stated plainly, because a guardrail that hides its failure modes is worse than none:

1. **Verbatim faithfulness ≠ semantic correctness.** A rule can quote the CFR
   exactly and still encode the wrong legal conclusion. The faithfulness gate
   will pass it ([§5](#5-the-faithfulness-gate)).
2. **Deterministic tag-matching can mis-route novel phrasing.** Routing depends
   on a fixed set of `triggers` and the structured fields of a
   `ConsultationRequest`. A real query phrased outside those tags can land on the
   wrong cascade — or on the deny-by-default path — for the wrong reason.
3. **The LLM renderer can still mis-phrase a correct decision.** The engine
   decides deterministically before any model call; the LLM only renders the
   reply. A correct `block`/`escalate` decision can still be worded misleadingly.
   The decision is reproducible without the model; the prose is not guaranteed
   faithful to it.
4. **Subset coverage.** Only eight sections are encoded and only 31 of 37 rules
   have a golden scenario. A situation governed by an unencoded section, or an
   encoded-but-untested rule, has no verified behavior here
   ([§2](#2-scope-boundary), [§4](#4-coverage-and-gaps)).

## 8. Reproducibility

Every number above is regenerated by the following commands from a fresh clone
(`uv sync --extra dev` first). None of them require an API key.

```bash
# Faithfulness: each rule's source_quote is verbatim CFR (substring OR coverage >= 0.85)
uv run regrails check faithfulness

# Coverage: rebuild the rule -> scenario matrix and the covered/total/gap counts
uv run regrails coverage report

# Full test suite (golden corpus + tamper-detection)
uv run pytest -q

# Hash-chained decision provenance: recompute the chain and detect any edit/insert/delete
uv run regrails audit verify demo/recorded-runs/decisions.chain.jsonl
```

The encoded rules live in `data/encoded/`, the bundled verbatim CFR text in
`data/cfr/`, the labeled scenarios in `tests/golden/`, and the research
snapshots in `research/snapshots/`. [`COVERAGE.md`](COVERAGE.md) is the
generated output of the second command and the authoritative source for the
coverage numbers.
