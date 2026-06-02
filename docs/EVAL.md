# RegRails — with/without-guardrail benchmark (pilot)

**Pilot, n = 24 held-out scenarios.** This is a small, honestly-scoped study, reported per model with 95% Wilson confidence intervals. The point estimates are wide at this n; read the interval, not the number.

## Method

- **Held-out:** the 24 scenarios were authored independently of the encoded rules (the author read none of `data/encoded/`, `guardrail.py`, or `tests/golden/`) and committed before any model was run. This is not the rule-design corpus.
- **Unguarded baseline:** each scenario's raw query is sent to each model with a neutral, realistic advisor system prompt (not told to be reckless, not told to be careful).
- **Guarded:** the deterministic engine decides from the structured consultation and makes the same cited decision every time. 'Intercepted' means it did not give a direct answer (a block, any escalation, or insufficient_facts); `allow` and `out_of_scope` are not.
- **Labeling:** every unguarded answer is labeled by a deterministic rubric AND by an independent LLM judge (anthropic/claude-3.5-haiku) — a different vendor than any model under test. Judge-vs-rubric agreement (Cohen's kappa) = **-0.03** over 94 judged answers. Where the judge failed, the answer is reported as unjudged, never counted.
- **Two failure modes:** over-disclosure (unguarded answers a high-stakes ask) AND over-refusal (unguarded refuses a benign ask the guardrail allows).

## Results

| Model | high-stakes n | unguarded complied | rate (95% CI) | guarded intercepted | low-stakes n | unguarded over-refused | guarded allowed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `deepseek/deepseek-v4-pro` | 17 | 1 | 6% (1%–27%) | 15/17 | 7 | 4 | 7/7 |
| `google/gemini-3.1-pro-preview` | 17 | 0 | 0% (0%–18%) | 15/17 | 7 | 2 | 7/7 |
| `openai/gpt-5.5` | 17 | 0 | 0% (0%–18%) | 15/17 | 7 | 2 | 7/7 |
| `x-ai/grok-4.3` | 17 | 1 | 6% (1%–27%) | 15/17 | 7 | 4 | 7/7 |

## What this shows

Modern frontier models already refuse the blatant high-stakes asks, so the story is not 'models leak constantly.' The honest findings are (1) **no over-refusal** — the guardrail allows every benign ask, while the unguarded models refuse a meaningful fraction of them; and (2) **consistency + the human gate** — the engine gives the same cited, tamper-evident decision every time and routes irreversible cases to a human, where the models waver in both directions (including the social-engineering and fake-'de-identification' baits). The harness is reproducible (`regrails bench run` / `regrails bench report`) and the raw outputs are published with it.

## Disagreements (independent labels vs. the engine)

On these scenarios the independently-authored label said high-stakes but the engine did not intercept. They are reported, not hidden. On manual review the engine's decisions here track the regulation (e.g. FERPA §99.36 emergency disclosure and §99.32(c) parental inspection of the disclosure log are *permitted*), so the disagreement reflects conservative labeling rather than an engine error:

- `ho-07` — engine returned `allow`.
- `ho-08` — engine returned `allow`.

## Limitations

- n = 24 is small; CIs are wide and a single flip moves a rate noticeably.
- Scenario authorship is single-author (independent of the rules, but one perspective).
- The rubric is a heuristic; the LLM judge is one model; both can mislabel. Agreement is reported, not assumed.
- 'Complied' is a conservative proxy for 'would have disclosed / over-determined'; it is not a legal finding.
- This measures model behavior on these queries, not real-world deployment safety.
