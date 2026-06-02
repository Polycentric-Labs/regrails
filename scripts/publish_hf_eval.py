"""Publish the RegRails eval to HuggingFace as a public dataset.

Default target: ``Polycentric-Labs/regrails-eval``. The HF token is read from
``HF_TOKEN`` in the environment OR from ``~/.secrets/huggingface.env`` (file-to-file;
never passed as an argument, never echoed). Dry-run by default — pass ``--live`` to
actually create the repo and upload.

Usage:
    python scripts/publish_hf_eval.py            # dry-run: shows what would upload
    python scripts/publish_hf_eval.py --live     # create_repo + upload (needs token)
"""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path

DEFAULT_REPO = "Polycentric-Labs/regrails-eval"
ROOT = Path(__file__).resolve().parent.parent

FILES = {
    "scenarios.heldout.jsonl": ROOT / "bench" / "scenarios.heldout.jsonl",
    "results.jsonl": ROOT / "bench" / "results.jsonl",
    "EVAL.md": ROOT / "docs" / "EVAL.md",
}

README_CARD = """---
license: apache-2.0
language: [en]
tags: [ferpa, title-iv, policy-as-code, ai-governance, guardrails, evaluation]
pretty_name: RegRails guardrail eval (pilot)
---

# RegRails guardrail eval (pilot)

Held-out scenarios and with/without-guardrail results for
[RegRails](https://github.com/Polycentric-Labs/regrails) — a FERPA + Title IV
policy-as-code AI guardrail. See `EVAL.md` for the method, the independent-judge
labeling, Cohen's kappa agreement, and the limitations. All data is synthetic.
This is a pilot (n = 24); read the confidence intervals, not the point estimates.
"""


def load_token(env_file: str | None = None) -> str:
    tok = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if tok:
        return tok
    path = Path(env_file or os.environ.get("HF_ENV_FILE", Path.home() / ".secrets" / "huggingface.env"))
    if not path.exists():
        raise FileNotFoundError(f"HF token not in env and env file not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*HF_TOKEN\s*=\s*(.+)\s*$", line)
        if m:
            val = m.group(1).strip().strip('"').strip("'")
            if val:
                return val
    raise RuntimeError(f"HF_TOKEN line not found in {path}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="Actually create_repo + upload.")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    args = ap.parse_args()

    missing = [name for name, p in FILES.items() if not p.exists()]
    if missing:
        raise SystemExit(f"Cannot publish — missing files: {missing}. Run `regrails bench run` first.")

    print(f"Repo: {args.repo} (public dataset)")
    for name, p in FILES.items():
        print(f"  upload {p}  ->  {name}  ({p.stat().st_size} bytes)")
    print("  upload README.md (dataset card)")

    if not args.live:
        print("\nDRY-RUN. Re-run with --live to create the repo and upload (needs HF token).")
        return

    token = load_token()
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(args.repo, repo_type="dataset", exist_ok=True, private=False)
    for name, p in FILES.items():
        api.upload_file(
            path_or_fileobj=str(p), path_in_repo=name, repo_id=args.repo, repo_type="dataset"
        )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(README_CARD)
        card_path = fh.name
    api.upload_file(
        path_or_fileobj=card_path, path_in_repo="README.md", repo_id=args.repo, repo_type="dataset"
    )
    print(f"\nPublished: https://huggingface.co/datasets/{args.repo}")


if __name__ == "__main__":
    main()
