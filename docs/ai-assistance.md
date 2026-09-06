# AI assistance in RegRails's development

Last updated: 2026-09-06. Disclosure level: **ai-assisted** (human work completed
with AI assistance and reviewed by the maintainer before it ships).

This page records how AI tools take part in building RegRails. It covers the
development process only. RegRails's own runtime use of a language model, and
its documented limits, are covered separately in [`METHODOLOGY.md`](METHODOLOGY.md)
(the model renders the reply only; the deterministic engine decides before any
model call) and in the README's own [Limitations](../README.md#limitations)
section.

## What the maintainer does

- Sets scope, priorities and design, and decides what ships and when.
- Reviews every change before it lands, runs the release review, and performs
  every publish step personally (tags, pushes, merges, and signed PyPI
  releases).
- Writes the security dispositions, licence decisions and public statements.

## Where AI tools help

| Role in the development workflow | Tools |
|---|---|
| Coding assistants (implementation, tests, refactors, drafting docs) | Claude Code |
| Hosted models, reached through a router | OpenRouter |
| Research and source discovery | Perplexity Sonar (Deep Research + Pro) |

The list changes as tools enter or leave the workflow; the date at the top is the
last revision. Custom infrastructure and integrations for each tool were built
in-house.

Hosted models also appear inside RegRails itself, in a different capacity than
the table above. The held-out benchmark in [`EVAL.md`](EVAL.md) scores several
unguarded comparison models against the guardrail (the README and `EVAL.md` name
them), with the results labeled by an independent Claude judge. The encoded FERPA
and Title IV rules were separately grounded by research streams from Perplexity
Sonar deep research together with a multi-model triangulation, committed in
[`research/snapshots/`](../research/snapshots/). Those two uses are the project's
own research and evaluation method, not tools used to build it.

## What is excluded

- No AI identity appears in git metadata. Commits are authored and signed by the
  maintainer, and there are no `Co-authored-by` trailers naming AI tools.
- No autonomous agent opens issues or pull requests, and none publishes anything.
- No AI-drafted text ships unread. Every document, changelog entry and release
  note is reviewed and edited by the maintainer first.

## Contributors

External contributors may use AI tools under the rules in
[`CONTRIBUTING.md`](../CONTRIBUTING.md): the contributor is the author and is
accountable for the change; significant AI assistance is disclosed in the pull
request description or with an `Assisted-by:` commit trailer; `Co-authored-by`
trailers naming AI tools are not accepted.

## Organisation policy

Polycentric Labs maintains one AI-assistance policy shared by its projects,
published at [polycentriclabs.com/ai-policy](https://polycentriclabs.com/ai-policy)
and mirrored in the organisation's GitHub profile as
[AI_POLICY.md](https://github.com/Polycentric-Labs/.github/blob/main/AI_POLICY.md).
This page is the project-level record under that policy.
