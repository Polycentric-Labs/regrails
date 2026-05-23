"""Tests for regrails.research — secret loading + HTTP shape (mocked)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from regrails.research import (
    OpenRouterError,
    chat_completion,
    load_api_key,
    run_research_stream,
)

# ---------------------------------------------------------------------------
# load_api_key
# ---------------------------------------------------------------------------


class TestLoadApiKey:
    def test_uses_env_var_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-fake-env")
        assert load_api_key() == "sk-or-fake-env"

    def test_reads_from_env_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        envfile = tmp_path / "openrouter.env"
        envfile.write_text("# header comment\nOPENROUTER_API_KEY=sk-or-fake-file\n")
        assert load_api_key(env_file=envfile) == "sk-or-fake-file"

    def test_strips_quotes_from_env_file_values(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        envfile = tmp_path / "openrouter.env"
        envfile.write_text('OPENROUTER_API_KEY="sk-or-quoted"\n')
        assert load_api_key(env_file=envfile) == "sk-or-quoted"

    def test_missing_file_raises(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(FileNotFoundError):
            load_api_key(env_file=tmp_path / "nope.env")

    def test_file_without_key_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        envfile = tmp_path / "openrouter.env"
        envfile.write_text("OTHER_THING=value\n# comment\n\n")
        with pytest.raises(OpenRouterError):
            load_api_key(env_file=envfile)


# ---------------------------------------------------------------------------
# chat_completion (mocked httpx)
# ---------------------------------------------------------------------------


def _make_mock_client(responder: object) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(responder))  # type: ignore[arg-type]


class TestChatCompletion:
    def test_happy_path(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            assert body["model"] == "perplexity/sonar-pro"
            assert body["messages"][0]["content"] == "hello"
            assert request.headers["authorization"] == "Bearer sk-or-test"
            assert "Polycentric-Labs/regrails" in request.headers["http-referer"]
            return httpx.Response(
                200,
                json={
                    "id": "resp-1",
                    "model": "perplexity/sonar-pro",
                    "choices": [{"message": {"role": "assistant", "content": "hi back"}}],
                    "citations": ["https://example.test/1"],
                    "usage": {"cost": 0.012},
                },
            )

        with _make_mock_client(respond) as client:
            result = chat_completion(
                model="perplexity/sonar-pro",
                messages=[{"role": "user", "content": "hello"}],
                api_key="sk-or-test",
                http_client=client,
            )
        assert result["choices"][0]["message"]["content"] == "hi back"
        assert result["citations"] == ["https://example.test/1"]

    def test_non_200_raises(self) -> None:
        def respond(_: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="upstream broke")

        with _make_mock_client(respond) as client:
            with pytest.raises(OpenRouterError, match="500"):
                chat_completion(
                    model="x",
                    messages=[{"role": "user", "content": "x"}],
                    api_key="sk-or-test",
                    http_client=client,
                )

    def test_malformed_response_raises(self) -> None:
        def respond(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"weird": "shape"})

        with _make_mock_client(respond) as client:
            with pytest.raises(OpenRouterError, match="Malformed"):
                chat_completion(
                    model="x",
                    messages=[{"role": "user", "content": "x"}],
                    api_key="sk-or-test",
                    http_client=client,
                )


# ---------------------------------------------------------------------------
# run_research_stream
# ---------------------------------------------------------------------------


class TestRunResearchStream:
    def test_builds_snapshot(self, tmp_path: Path) -> None:
        def respond(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "found stuff"}}
                    ],
                    "citations": [
                        {"url": "https://www.ed.gov/ferpa", "title": "PTAC guidance"}
                    ],
                    "usage": {"total_cost_usd": 0.05},
                },
            )

        sink = tmp_path / "audit.jsonl"
        with _make_mock_client(respond) as client:
            snap = run_research_stream(
                stream_name="ferpa-test",
                query="What's the standard?",
                model="perplexity/sonar-pro",
                api_key="sk-or-test",
                audit_sink=sink,
                http_client=client,
            )

        assert snap.response_text == "found stuff"
        assert snap.citations == [
            {"url": "https://www.ed.gov/ferpa", "title": "PTAC guidance"}
        ]
        assert snap.cost_usd == 0.05
        assert snap.id.startswith("ferpa-test-")
        # Audit emitted
        assert sink.exists()
        lines = sink.read_text(encoding="utf-8").splitlines()
        assert any("research.stream_fetched" in line for line in lines)

    def test_failure_emits_failure_audit_and_reraises(self, tmp_path: Path) -> None:
        def respond(_: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="rate limited")

        sink = tmp_path / "audit.jsonl"
        with _make_mock_client(respond) as client, pytest.raises(OpenRouterError):
            run_research_stream(
                stream_name="boom",
                query="x",
                model="perplexity/sonar-pro",
                api_key="sk-or-test",
                audit_sink=sink,
                http_client=client,
            )
        assert sink.exists()
        assert "research.stream_failed" in sink.read_text(encoding="utf-8")
