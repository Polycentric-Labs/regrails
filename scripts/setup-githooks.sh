#!/usr/bin/env bash
# S6 — one-time git-hooks installer for RegRails.
#
# Points git at the in-repo .githooks/ directory so the committed commit-msg gate
# (capitalized subject + no AI-attribution trailers) runs on every commit. Hooks
# live IN the repo (under version control) instead of the un-tracked .git/hooks/,
# so every clone gets the same gate after running this once.
#
# Run from the repo root:
#     bash scripts/setup-githooks.sh

set -euo pipefail

# Resolve the repo root from this script's location (scripts/ is one level down).
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
cd "$repo_root"

hooks_dir=".githooks"

if [ ! -d "$hooks_dir" ]; then
  echo "setup-githooks: '$hooks_dir' not found at repo root ($repo_root)." >&2
  exit 1
fi

git config core.hooksPath "$hooks_dir"

# Make every hook executable (no-op on Windows filesystems, harmless elsewhere).
chmod +x "$hooks_dir"/* 2>/dev/null || true

echo "setup-githooks: core.hooksPath -> $hooks_dir"
echo "setup-githooks: active hooks:"
for h in "$hooks_dir"/*; do
  [ -f "$h" ] && echo "  - $(basename "$h")"
done
echo "setup-githooks: done. The commit-msg gate is now active for this clone."
