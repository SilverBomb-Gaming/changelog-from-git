"""Provider selection and response parsing. HTTP is mocked; Ollama is not started."""

from __future__ import annotations

import json

import httpx
import pytest

from git_changelog.errors import LLMError
from git_changelog.llm import OllamaClient, OpenAICompatibleClient, build_client


def test_build_client_defaults_to_local_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHANGELOG_PROVIDER", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    client = build_client()
    assert isinstance(client, OllamaClient)
    assert client.model == "llama3.2"
    assert client.base_url == "http://127.0.0.1:11434"
    client.close()


def test_openai_cloud_requires_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        build_client("openai")


def test_local_openai_compatible_server_may_omit_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = build_client("openai", model="local-model")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "local-model"
    assert client.api_key == ""
    client.close()


def test_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(LLMError, match="ollama"):
        build_client("anthropic")


def test_timeout_must_be_a_positive_number(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHANGELOG_TIMEOUT", "soon")
    with pytest.raises(LLMError, match="CHANGELOG_TIMEOUT"):
        build_client()
    monkeypatch.setenv("CHANGELOG_TIMEOUT", "0")
    with pytest.raises(LLMError, match="positive"):
        build_client()


def test_ollama_complete_parses_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content.decode())
        assert body["model"] == "llama3.2"
        assert body["stream"] is False
        assert body["format"] == "json"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json={"message": {"content": "{\"sections\": []}"}})

    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        timeout=5,
        num_ctx=8192,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.complete(system="rules", user="commits") == "{\"sections\": []}"
    client.close()


def test_ollama_missing_model_mentions_pull() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        timeout=5,
        num_ctx=8192,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMError, match="ollama pull llama3.2"):
        client.complete(system="rules", user="commits")
    client.close()


def test_openai_complete_reads_the_first_choice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        body = json.loads(request.content.decode())
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"sections\": []}"}}]},
        )

    client = OpenAICompatibleClient(
        base_url="http://127.0.0.1:1234/v1",
        api_key="test-key",
        model="local-model",
        timeout=5,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.complete(system="rules", user="commits") == "{\"sections\": []}"
    client.close()
