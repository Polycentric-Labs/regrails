# Changelog

All notable changes to RegRails are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.4.0 - 2026-06-02

### Web platform + airtight validation + release safeguards

#### Added

- **Web platform — a 10-route React SPA** (Vite + React + TypeScript) presenting
  the whole RegRails surface as a live, clickable site:
  - **Live consult demo** — type a query and structured fields; the page runs the
    deterministic engine first (`/api/decide`), then optionally renders the advisor
    reply (`/api/reply`), showing the engine -> advisor flow with the engine's
    decision authoritative.
  - **Rules browser** — all 37 rules across FERPA + Title IV, each with its
    citation, risk tier, human-gate flag, and the verbatim CFR section text + hash.
  - **Coverage** — the 31/37 rule-to-scenario matrix and the 6 uncovered gap IDs
    with rationale.
  - **Benchmark** — the held-out eval results (per-model unguarded-comply rates with
    Wilson CIs, the honest disagreements surfaced rather than hidden).
  - **Provenance** — a live hash-chain verifier: paste a decision log and get the
    same tamper-evident verdict the CLI produces.
  - **Exports** — OSCAL 1.1.2 and SARIF 2.1.0 viewers over the engine's own output.
  - **MCP** and **Action** docs, plus **Methodology** and **About**.
- **Serverless functions** (Vercel Python) backing the site:
  - `/api/decide` — the engine-only consultation endpoint (no LLM, no key).
  - `/api/verify` — verifies a hash-chained decision log by reusing the package's
    own `regrails.audit.verify_chain`, so the web verdict matches the CLI exactly.
  - `/api/reply` — the **engine-gated** live advisor reply: only `allow` /
    `out_of_scope` outcomes may reach the LLM; every other outcome returns a
    deterministic templated message with no model call. Request bodies are capped
    (64 KiB) and the LLM-bound query is clamped (8 KiB) to bound token spend; the
    page always degrades gracefully (templated reply) when no key is present.
- **`py.typed` marker** shipped in the package, so `regrails` type-checks as a typed
  package downstream — making the `Typing :: Typed` classifier honest.
- **`CHANGELOG.md`** (this file).

#### Changed

- **Anti-drift data pipeline.** The website renders the package's *own* generated
  JSON (`web/public/data/*`), produced by `scripts/gen_web_data.py` from the same
  loaders, OSCAL/SARIF emitters, bench-report statistics, and `audit.append_decision`
  hash-chaining the CLI uses. A parity gate (`tests/test_web_data_parity.py`) fails
  if the committed data drifts byte-for-byte from a fresh build, so a stale website
  can never merge — the site cannot diverge from the CLI.
- **Shared `normalize_consultation` helper.** The consultation normalizer now lives
  once in `regrails.guardrail` and is imported by both `/api/decide` and
  `/api/reply`, replacing the duplicate copies the two endpoints used to carry.

#### Release safeguards (S1-S7, see `docs/SAFEGUARDS.md`)

- **Tag-time gate (S2)** — the PyPI publish job now `needs:` a gate that runs ruff +
  mypy + pytest + version-consistency on the tagged commit, so **a red tree can
  never become a published release**.
- **Version-consistency check** — `scripts/check_version_consistency.py` asserts the
  three independent version declarations (`regrails.__version__`, `pyproject.toml`,
  and the `regrails==` pin in `web/requirements.txt`) agree, failing closed on drift.
- **CLI<->web parity check** — `scripts/check_parity.py` enforces a parity manifest
  against the live Typer tree and the web route registry: every CLI leaf must be
  accounted for, every mapped web route must exist, and parity debt may shrink but
  never grow.
- **CI mirrors** — the continuous test gate, the anti-drift consistency gate, and
  the action self-test run the same checks the local release runbook does.
- **Secret scan** — gitleaks runs over full history on push/PR.
- **Commit-message hook** — `.githooks/commit-msg` (opt-in via
  `scripts/setup-githooks.sh`) rejects a lowercase subject and any AI-attribution /
  co-authorship trailer at commit time.
- **Signed, attested publish (S7)** — PyPI Trusted Publisher (OIDC, no long-lived
  token) + SLSA build provenance + PEP 740 attestations.
