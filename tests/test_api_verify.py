"""Tests for the /api/verify Vercel serverless function (web/api/verify.py).

Self-contained: the Vercel function lives in ``web/api`` (outside the package
import root), so this module prepends that dir to ``sys.path`` itself rather than
relying on a shared conftest. It then verifies that ``verify_payload`` reuses the
package's ``regrails.audit.verify_chain`` — guaranteeing CLI/web parity.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "api"))

import verify  # noqa: E402

from regrails.audit import append_decision  # noqa: E402


def _decision(i: int) -> dict[str, object]:
    return {"id": f"dec-{i}", "outcome": "block", "citations_emitted": ["34-CFR-99.30"]}


def _valid_chain_text(tmp_path: Path, n: int = 2) -> str:
    """Build an ``n``-record valid hash chain on disk and return its raw text."""
    sink = tmp_path / "chain.jsonl"
    for i in range(n):
        append_decision(_decision(i), sink)
    return sink.read_text(encoding="utf-8")


class TestVerifyPayload:
    def test_valid_chain_verifies(self, tmp_path: Path) -> None:
        text = _valid_chain_text(tmp_path, n=2)
        assert verify.verify_payload(text) == (True, [])

    def test_tampered_chain_fails(self, tmp_path: Path) -> None:
        text = _valid_chain_text(tmp_path, n=2)
        # Tamper an outcome value via a plain string replace — breaks the record_hash.
        tampered = text.replace('"outcome":"block"', '"outcome":"allow"', 1)
        assert tampered != text  # sanity: the replace actually fired
        ok, problems = verify.verify_payload(tampered)
        assert ok is False
        assert problems  # non-empty

    def test_empty_string_does_not_crash(self) -> None:
        ok, problems = verify.verify_payload("")
        assert ok is False
        assert problems  # a problem message, not a traceback

    def test_garbage_input_does_not_crash(self) -> None:
        ok, problems = verify.verify_payload("not json at all\n{broken")
        assert ok is False
        assert problems


class TestExtractChainText:
    """``_extract_chain_text`` accepts either a ``{"log": "..."}`` JSON wrapper or
    the raw chain text. ``decoded`` is already a ``str`` (``bytes.decode`` with
    ``errors="replace"`` never raises), so the only parse failure is a
    ``JSONDecodeError`` — finding #6 removed the unreachable ``UnicodeDecodeError``.
    """

    def test_json_wrapper_returns_log_value(self) -> None:
        raw = b'{"log": "record-1\\nrecord-2"}'
        assert verify._extract_chain_text(raw) == "record-1\nrecord-2"

    def test_non_json_body_returned_verbatim(self) -> None:
        # Not JSON -> the JSONDecodeError branch returns the decoded text as-is.
        raw = b"this is a raw chain line\n{still not valid json"
        assert verify._extract_chain_text(raw) == "this is a raw chain line\n{still not valid json"

    def test_json_without_log_key_returned_verbatim(self) -> None:
        raw = b'{"notlog": 1}'
        assert verify._extract_chain_text(raw) == '{"notlog": 1}'

    def test_invalid_utf8_bytes_do_not_crash(self) -> None:
        # errors="replace" means undecodable bytes become U+FFFD rather than raising;
        # the result still flows through json.loads -> JSONDecodeError -> verbatim.
        raw = b"\xff\xfe bad bytes not json"
        out = verify._extract_chain_text(raw)
        assert isinstance(out, str)  # no crash, a string came back
