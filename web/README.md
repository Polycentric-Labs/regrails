# RegRails live demo (Vercel)

A one-page demo of the **deterministic guardrail engine**. You type a query and a
few structured fields; a Python serverless function (`api/decide.py`) runs
`regrails`'s `decide()` — **no LLM, no API key** — and returns the typed
`GuardrailDecision` (outcome, risk tier, human-gate flag, citations). Synthetic
data only; this demonstrates the engine that decides *before* any model speaks.

## Deploy

The Vercel project's **Root Directory** must be set to `web/`.

```bash
vercel link            # link the repo; set Root Directory = web/
vercel deploy --prod   # build + deploy
```

The serverless function installs `regrails` from PyPI via `requirements.txt`
(`regrails==0.3.1`). No environment variables are needed — the engine has no LLM
and no secrets.

## Files

- `index.html` — the single-page UI (preset scenarios + a form).
- `api/decide.py` — the engine-only serverless endpoint (`POST /api/decide`).
- `requirements.txt` — pins the published `regrails` package.
- `vercel.json` — serves `index.html` at `/`.
