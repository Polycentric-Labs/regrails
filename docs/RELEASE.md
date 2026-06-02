# RegRails release runbook

RegRails ships to PyPI on a **tag push**. Pushing an annotated, signed tag like
`v0.4.0` triggers `.github/workflows/release.yml`, which runs the tag-time gate
(S2), then builds, attests (SLSA + PEP 740), and publishes via a PyPI **Trusted
Publisher** (OIDC — no long-lived token). **Push-to-`main` does not publish; only a
`v*` tag does.**

> The PUSH is the gate. Local commits and a local tag are reversible; the push that
> fires `release.yml` is the irreversible, public step. Get explicit approval before
> pushing a tag.

## Before you tag — local gates

Run from the repo root. (Set `PYTHONIOENCODING=utf-8` first on Windows.)

```bash
uv sync --extra dev

uv run ruff check .
uv run mypy
uv run pytest -ra -q
uv run python scripts/check_version_consistency.py
uv run python scripts/check_parity.py
uv run python scripts/check_docs_links.py
uv run pytest tests/test_web_data_parity.py -ra -q

# Faithfulness + provenance (same checks test.yml runs):
uv run regrails check faithfulness --verbose
uv run regrails coverage report
uv run regrails audit verify demo/recorded-runs/decisions.chain.jsonl
```

These mirror the CI gates (S1 + S2 + S3). If `web/public/data` is stale, regenerate
and commit it:

```bash
uv run python scripts/gen_web_data.py web/public/data
```

## Bump the version

Edit the single source of truth and keep the literals in lockstep (S3 enforces
this):

1. `pyproject.toml` → `[project].version`
2. anywhere else `check_version_consistency.py` checks (run it to confirm).

Commit the bump with a capitalized subject and **no AI-attribution trailer** (S6
enforces both):

```bash
git add -A
git commit -m "Release vX.Y.Z"
```

## Tag + push (the gated, approval-required step)

RegRails tags are **signed and annotated**:

```bash
git tag -s vX.Y.Z -m "RegRails vX.Y.Z"
git push origin vX.Y.Z          # <-- fires release.yml; requires explicit approval
```

On the tag push, `release.yml`:

1. **`gate` job (S2)** — ruff + mypy + pytest + `check_version_consistency.py`.
   A failure here **blocks** the publish job (`release` declares `needs: gate`).
2. **`release` job (S7)** — `uv build` → `actions/attest-build-provenance` (SLSA)
   → `pypa/gh-action-pypi-publish` (Trusted Publisher + PEP 740 attestations).

If the gate is red, fix forward, delete the bad tag, and re-tag — never bypass the
gate to force a publish.

## Step 7 — post-publish verification checklist

After `release.yml` succeeds, verify the published artifact before announcing it.

- [ ] **CI green.** The `gate` job and the `release` job both succeeded in the
      Actions run for the tag.
- [ ] **On PyPI.** `https://pypi.org/project/regrails/X.Y.Z/` exists; the version
      matches the tag.
- [ ] **PEP 740 attestations present.** PyPI shows attestations for the wheel +
      sdist (Trusted-Publisher provenance).
- [ ] **SLSA build provenance verifies.**
      `gh attestation verify --owner Polycentric-Labs <downloaded-wheel>`.
- [ ] **Fresh install works.** In a clean venv:
      `pip install regrails==X.Y.Z` then `regrails check faithfulness` → 37/37,
      and `regrails --version` (or equivalent) reports `X.Y.Z`.
- [ ] **Dependency vulnerability scan clean (manual gate).**
      `osv-scanner --lockfile uv.lock` reports no actionable findings. (Not yet a
      CI gate — see [SAFEGUARDS.md](SAFEGUARDS.md).)
- [ ] **Version consistency green at the tag.**
      `uv run python scripts/check_version_consistency.py`.
- [ ] **Tag is signed + annotated.** `git tag -v vX.Y.Z` verifies the signature.

## If something goes wrong

- **Gate failed after tagging.** Delete the tag locally and (with approval) on the
  remote, fix forward on `main`, re-bump if needed, re-tag.
  `git tag -d vX.Y.Z` and — approval-gated — `git push origin :refs/tags/vX.Y.Z`.
- **Never move/force-update a published tag.** SLSA provenance + signatures bind to
  the tagged commit SHA; rewriting history invalidates them. Cut a new patch
  version instead.
- **Trusted-Publisher mismatch (`environment`).** If PyPI was configured to require
  an Environment, add a matching `environment:` block to the `release` job (the
  workflow has a NOTE comment at that spot). Registered without one → leave it off.

## Cross-references

- Full safeguard catalog: [SAFEGUARDS.md](SAFEGUARDS.md) (S1–S7).
- Methodology + limitations: [METHODOLOGY.md](METHODOLOGY.md).
- Eval + benchmark: [EVAL.md](EVAL.md).
