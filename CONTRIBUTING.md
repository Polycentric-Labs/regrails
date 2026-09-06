# Contributing to RegRails

RegRails is a proof-of-concept, Apache-2.0 licensed. Its core claims (rule
faithfulness, coverage, decision provenance) are meant to be checked, not
taken on faith, and contributions are expected to keep that property.

## Setup

```bash
git clone https://github.com/Polycentric-Labs/regrails.git && cd regrails
uv sync --extra dev
```

## Running the checks

```bash
uv run regrails check faithfulness   # 37/37 rules verbatim-faithful to the bundled CFR text
uv run regrails coverage report      # rule -> scenario traceability matrix
uv run pytest -q                     # 280 tests
```

Ruff and mypy (strict) are configured in `pyproject.toml` and run in CI.

If a change touches an encoded rule in `data/encoded/`, keep its `source_quote`
field verbatim to the bundled CFR text in `data/cfr/`: the faithfulness gate
checks this automatically and a rule that fails it will not merge.

## AI-assisted contributions

You may use AI tools while contributing. Two rules apply, and they mirror the
project's own disclosure in [`docs/ai-assistance.md`](docs/ai-assistance.md):

- **You are the author.** Understand the change and be able to explain it in
  your own words; review questions are answered by you, not by a tool. Pull
  requests opened by autonomous agents are closed.
- **Disclose significant assistance.** Say so in the pull request description,
  or add an `Assisted-by: <tool>` trailer to the commit message. Do not add
  `Co-authored-by` trailers naming AI tools: they create a contributor identity
  in the repository record, and only people are contributors here.
