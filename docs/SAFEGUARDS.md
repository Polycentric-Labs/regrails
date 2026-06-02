# RegRails release safeguards (S1–S7)

The catalog of automated gates that protect a RegRails release. Each safeguard is
a concrete, runnable check wired into CI, the release workflow, or a git hook — not
a policy statement. The design intent: **a red tree can never become a published
release.** The tag-time gate (S2) is the load-bearing one; the rest are defense in
depth.

| ID | Safeguard | Where | Trigger | Status |
|----|-----------|-------|---------|--------|
| **S1** | Continuous test gate — ruff + mypy-strict + pytest + faithfulness gate + coverage matrix + provenance-chain verify | `.github/workflows/test.yml` | push + PR to `main` | **Active** |
| **S2** | **Tag-time gate** — ruff + mypy + pytest + version-consistency must pass *before* PyPI publish (`release` job `needs: gate`) | `.github/workflows/release.yml` | `v*` tag push | **Active** |
| **S3** | Anti-drift consistency gate — version consistency + CLI↔web/docs parity + web-data byte-identity + in-repo doc-link check | `.github/workflows/consistency.yml` | push + PR to `main` | **Active** |
| **S4** | Secret scan — gitleaks over full history | `.github/workflows/secret-scan.yml` | push + PR to `main` | **Active** |
| **S5** | Composite-action self-test — a `block` decision must FAIL the gate; an out-of-scope decision must PASS | `.github/workflows/action-smoke.yml` | push touching `docs/action/**` | **Active** |
| **S6** | Commit-message gate — reject a lowercase subject; reject any AI-attribution / co-authorship trailer | `.githooks/commit-msg` (via `scripts/setup-githooks.sh`) | every `git commit` | **Active** (opt-in per clone) |
| **S7** | Signed, attested publish — PyPI Trusted Publisher (OIDC, no long-lived token) + SLSA build-provenance + PEP 740 attestations | `.github/workflows/release.yml` (`release` job) | `v*` tag push | **Active** |

## How the gates compose

```
git commit ──S6──▶ commit-msg gate (subject case + no AI attribution)
   │
   ▼
push / PR to main ──S1──▶ test.yml      (ruff · mypy · pytest · faithfulness · coverage · provenance)
                   ──S3──▶ consistency  (version · parity · web-data · doc-links)
                   ──S4──▶ secret-scan  (gitleaks)
                   ──S5──▶ action-smoke (composite-action block/pass self-test, when docs/action/** changes)
   │
   ▼
push tag vX.Y.Z ──S2──▶ gate job       (ruff · mypy · pytest · version-consistency)   ◀── BLOCKS publish if red
                          │  needs: gate
                          ▼
                 ──S7──▶ release job    (uv build · SLSA attest · Trusted-Publisher PyPI publish)
```

S2 is the key fix: the `release` job in `release.yml` declares `needs: gate`, so a
failing test/type/lint/version check on the tagged commit blocks the publish step
entirely. The publish job's OIDC / `id-token: write` / `attestations: write`
permissions and the Trusted-Publisher step (S7) are unchanged — S2 only adds the
dependency.

## Scripts the gates call

| Script | Used by | Purpose |
|--------|---------|---------|
| `scripts/check_version_consistency.py` | S2, S3 | Version literals agree (pyproject == built package == web, and the tag on a release). Non-zero exit on mismatch. |
| `scripts/check_parity.py` | S3 | The CLI feature surface and the web/docs surface have not diverged. Non-zero exit on drift. |
| `scripts/check_docs_links.py` | S3 | Every relative Markdown link in `README.md` + `docs/*.md` resolves to a real path. |
| `scripts/setup-githooks.sh` | S6 | One-time installer: points `core.hooksPath` at `.githooks/`. |
| `tests/test_web_data_parity.py` | S3 | The committed `web/public/data/*.json` is byte-identical to a fresh `gen_web_data.py` build. |

## Operating notes

- **S6 is opt-in per clone.** Git hooks are not auto-installed; run
  `bash scripts/setup-githooks.sh` once after cloning to activate the commit-msg
  gate. CI does not depend on it (it is a local fast-feedback layer; the CI gates
  above are the enforcement boundary).
- **osv / dependency-vulnerability scanning** is intentionally *not* in the CI gate
  set yet — RegRails CI has never run osv, so adding it here would be net-new
  scope. `osv-scanner --lockfile uv.lock` is listed in the local
  [RELEASE.md](RELEASE.md) Step-7 checklist as a manual pre-tag check; promote it to
  a CI job when the project is ready to own that gate.
- **gitleaks on an org repo** (Polycentric-Labs) requires a free `GITLEAKS_LICENSE`
  secret; the S4 workflow reads it from repo/org secrets and fails closed if absent.
