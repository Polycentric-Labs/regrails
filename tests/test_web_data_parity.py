"""Anti-drift gate: the committed ``web/public/data/*.json`` must equal a fresh build.

This is the whole point of the pipeline. The website ships the committed JSON; if
the ``regrails`` package's data, the bench results, the OSCAL/SARIF emitters, or
the docs change without someone regenerating ``web/public/data``, this test fails
and the stale website can never be merged. To fix a failure, run::

    uv run python scripts/gen_web_data.py web/public/data

and commit the regenerated files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.gen_web_data import build_web_data  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[1]
_COMMITTED_DIR = _REPO_ROOT / "web" / "public" / "data"
_FILES = (
    "rules.json",
    "coverage.json",
    "eval.json",
    "oscal.json",
    "sarif.json",
    "methodology.json",
)


@pytest.fixture(scope="module")
def fresh_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("web_data_fresh")
    build_web_data(out)
    return out


@pytest.mark.parametrize("name", _FILES)
def test_committed_web_data_matches_fresh_build(name: str, fresh_dir: Path) -> None:
    committed_path = _COMMITTED_DIR / name
    fresh_path = fresh_dir / name
    assert committed_path.exists(), (
        f"{name} is not committed under web/public/data — "
        f"run `uv run python scripts/gen_web_data.py web/public/data`"
    )

    committed = json.loads(committed_path.read_text(encoding="utf-8"))
    fresh = json.loads(fresh_path.read_text(encoding="utf-8"))
    assert committed == fresh, (
        f"{name} is STALE — the committed web data drifted from the package. "
        f"Regenerate with `uv run python scripts/gen_web_data.py web/public/data`."
    )


@pytest.mark.parametrize("name", _FILES)
def test_committed_web_data_is_byte_identical(name: str, fresh_dir: Path) -> None:
    """Stronger than ``==``: the committed bytes must match the deterministic
    serialisation exactly (sort_keys + indent=2 + trailing newline)."""
    committed_bytes = (_COMMITTED_DIR / name).read_bytes()
    fresh_bytes = (fresh_dir / name).read_bytes()
    assert committed_bytes == fresh_bytes, (
        f"{name} bytes differ from a fresh build — regenerate "
        f"`uv run python scripts/gen_web_data.py web/public/data`."
    )
