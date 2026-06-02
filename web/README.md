# RegRails web platform (Vercel)

The RegRails web console — a **React single-page app** that presents the whole
RegRails surface as a live, clickable site. It is built with **Vite + React +
TypeScript** and ships **10 routes**:

`/` live consult demo · `/rules` · `/coverage` · `/benchmark` · `/methodology` ·
`/provenance` · `/exports` · `/mcp` · `/action` · `/about`

The single source of truth for the route list is
[`src/routes/registry.tsx`](src/routes/registry.tsx) (both the router and the
nav-rail read it).

Synthetic data only — no real student records exist anywhere here.

## How it stays honest (anti-drift)

The site does **not** re-implement any of the engine in TypeScript. Instead it
renders the package's *own* generated JSON from
[`public/data/`](public/data/) — `rules.json`, `coverage.json`, `eval.json`,
`oscal.json`, `sarif.json`, `methodology.json`, and the
`provenance-sample.jsonl` hash chain. Those files are produced by
[`scripts/gen_web_data.py`](../scripts/gen_web_data.py) from the installed
`regrails` package (the same loaders, OSCAL/SARIF emitters, bench-report
statistics, and `audit.append_decision` hash-chaining the CLI uses). A parity
gate (`tests/test_web_data_parity.py`) fails CI if the committed data drifts
byte-for-byte from a fresh build, so the website can never diverge from the CLI.

Regenerate the data after any change to the package, bench results, or docs:

```bash
uv run python scripts/gen_web_data.py web/public/data
```

## Serverless functions

Three Python serverless functions (in [`api/`](api/)) back the dynamic routes.
Each one reuses the published `regrails` package (pinned in
[`requirements.txt`](requirements.txt)), so a web result always matches the CLI:

- **`api/decide.py`** — `POST /api/decide`. Runs the deterministic guardrail
  (`regrails.guardrail.decide`) on a consultation and returns the typed
  `GuardrailDecision`. **No LLM, no API key, no secrets.**
- **`api/verify.py`** — `POST /api/verify`. Verifies a hash-chained decision log
  via `regrails.audit.verify_chain` — the same verdict the CLI
  `regrails audit verify` produces.
- **`api/reply.py`** — `POST /api/reply`. The **optional, engine-gated** live
  advisor reply. It decides first; only `allow` / `out_of_scope` outcomes may
  reach the LLM, and every other outcome returns a deterministic templated
  message with no model call. Always degrades gracefully (templated reply) when
  no key is present, so the page never breaks.

Request bodies are size-capped before they are read (64 KiB), and the
LLM-bound query is clamped (8 KiB) to bound token spend.

## Develop

```bash
cd web
npm install
npm run dev          # Vite dev server
npm run build        # tsc --noEmit + vite build  ->  dist/
npm run typecheck    # tsc --noEmit
npm test             # vitest
npm run e2e          # Playwright
```

## Deploy

Deployed on **Vercel**. The project's **Root Directory must be set to `web/`**,
so Vercel finds this `package.json`, the `api/` functions, and
[`vercel.json`](vercel.json) (which serves the SPA and routes `/api/*` to the
functions).

```bash
vercel link            # link the repo; set Root Directory = web/
vercel deploy --prod   # build + deploy
```

The serverless functions install `regrails` from PyPI via `requirements.txt`.
**No environment variables are required** — `/api/decide` and `/api/verify` have
no LLM and no secrets, and `/api/reply` degrades to a templated reply when no key
is set. To enable the **live advisor reply** on `/api/reply`, set
`OPENROUTER_API_KEY` in the Vercel dashboard (it is read only from the
environment — never hardcoded, logged, or echoed back).
