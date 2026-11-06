from __future__ import annotations

import json

import httpx
import pytest

from app.agents.prompts import (
    REFUSAL_TEXT,
    build_answer_prompt,
    build_extract_prompt,
    build_route_prompt,
)
from app.config import Settings
from app.providers import ChatMessage, ProviderError, get_provider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compat import OpenAICompatProvider


def msg(text: str) -> list[ChatMessage]:
    return [ChatMessage("user", text)]


# ---------------------------------------------------------------- mock provider


def test_mock_answers_from_context_with_citation():
    prompt = build_answer_prompt(
        "How often should transformer oil be sampled?",
        [
            "[mm-transformer-oil#0] Take an oil sample from every power transformer every 12 "
            "months for dissolved gas analysis. Increase the frequency if a gas value is high."
        ],
        [],
    )
    result = get_provider("mock", Settings()).chat("mock-extractive", msg(prompt))
    assert "12 months" in result.text
    assert "[mm-transformer-oil#0]" in result.text


def test_mock_refuses_when_question_names_unknown_entity():
    prompt = build_answer_prompt(
        "Did we win the deal with Tokyo Metropolitan Grid?",
        ["[wl-008-helvetia#0] Helvetia Grid tendered switchgear. We won the deal."],
        [],
    )
    result = get_provider("mock", Settings()).chat("mock-extractive", msg(prompt))
    assert result.text == REFUSAL_TEXT


def test_mock_refuses_with_empty_context():
    prompt = build_answer_prompt("What is the CEO salary?", [], [])
    result = get_provider("mock", Settings()).chat("mock-extractive", msg(prompt))
    assert result.text == REFUSAL_TEXT


def test_mock_records_count_answer():
    prompt = build_answer_prompt(
        "How many deals did we lose?",
        ["[wl-001-nordgrid] Customer: Nordgrid Utilities | outcome: lost"],
        ["count=6"],
    )
    result = get_provider("mock", Settings()).chat("mock-extractive", msg(prompt))
    assert "6" in result.text and "[wl-001-nordgrid]" in result.text


def test_mock_route_uses_heuristic():
    prompt = build_route_prompt(
        "How many deals did we lose to VoltEdge?", ["VoltEdge", "GridCore"], ["Asia Pacific"]
    )
    data = json.loads(get_provider("mock", Settings()).chat("mock-extractive", msg(prompt)).text)
    assert data["tool"] == "query_records"
    assert data["args"] == {"aggregate": "count", "outcome": "lost", "competitor": "VoltEdge"}


def test_mock_extract_returns_json():
    report = "# Win/Loss Report: Acme\n\nOutcome: Won\nOur price: EUR 1,000"
    data = json.loads(
        get_provider("mock", Settings())
        .chat("mock-extractive", msg(build_extract_prompt(report)))
        .text
    )
    assert data["customer"] == "Acme"
    assert data["outcome"] == "won"
    assert data["our_price_eur"] == 1000.0


def test_mock_unknown_model_is_an_error():
    with pytest.raises(ProviderError):
        get_provider("mock", Settings()).chat("gpt-99", msg("hi"))


def test_provider_status_covers_every_provider_and_works_without_servers(monkeypatch):
    from app import providers

    class Down:
        def is_available(self) -> bool:
            return False

        def list_models(self) -> list[str]:
            return []

    real = providers.get_provider
    monkeypatch.setattr(
        providers,
        "get_provider",
        lambda name, s, t=None: real(name, s) if name == "mock" else Down(),
    )
    status = providers.provider_status(Settings())
    assert list(status) == list(providers.PROVIDER_NAMES)
    assert status["mock"]["available"] is True
    assert status["mock"]["models"] == ["mock-extractive", "mock-sloppy"]
    assert status["ollama"] == {"available": False, "models": []}


def test_unknown_provider_is_an_error():
    with pytest.raises(ProviderError):
        get_provider("nope", Settings())


def test_sloppy_model_is_deterministic():
    prompt = build_answer_prompt(
        "How often should transformer oil be sampled?",
        ["[mm-transformer-oil#0] Take an oil sample every 12 months for gas analysis."],
        [],
    )
    provider = get_provider("mock", Settings())
    a = provider.chat("mock-sloppy", msg(prompt)).text
    b = provider.chat("mock-sloppy", msg(prompt)).text
    assert a == b


# ------------------------------------------------------------ ollama (mocked http)


def test_ollama_chat_parses_speed_and_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/api/chat"
        assert body["stream"] is False
        assert body["format"] == "json"
        return httpx.Response(
            200,
            json={
                "message": {"content": "hello"},
                "prompt_eval_count": 12,
                "eval_count": 50,
                "eval_duration": 1_000_000_000,
            },
        )

    provider = OllamaProvider("http://x", transport=httpx.MockTransport(handler))
    result = provider.chat("llama3.2", msg("hi"), json_mode=True)
    assert result.text == "hello"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 50
    assert result.tokens_per_second == pytest.approx(50.0)


def test_ollama_http_error_becomes_provider_error():
    transport = httpx.MockTransport(
        lambda r: httpx.Response(404, json={"error": "model not found"})
    )
    provider = OllamaProvider("http://x", transport=transport)
    with pytest.raises(ProviderError, match="model not found"):
        provider.chat("nope", msg("hi"))


def test_connection_errors_become_provider_errors():
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    transport = httpx.MockTransport(boom)
    with pytest.raises(ProviderError, match="Could not reach Ollama"):
        OllamaProvider("http://x", transport=transport).chat("m", msg("hi"))
    with pytest.raises(ProviderError, match="Could not reach llamacpp"):
        OpenAICompatProvider("llamacpp", "http://x/v1", transport=transport).chat("m", msg("hi"))


def test_ollama_lists_models_and_reports_unavailable():
    ok = httpx.MockTransport(lambda r: httpx.Response(200, json={"models": [{"name": "llama3.2"}]}))
    provider = OllamaProvider("http://x", transport=ok)
    assert provider.list_models() == ["llama3.2"]
    assert provider.is_available()

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    down = OllamaProvider("http://x", transport=httpx.MockTransport(boom))
    assert down.list_models() == []
    assert not down.is_available()


# ------------------------------------------------------ openai compatible (mocked http)


def test_openai_compat_chat():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3},
            },
        )

    provider = OpenAICompatProvider(
        "nim",
        "http://x/v1",
        api_key="secret",
        requires_key=True,
        transport=httpx.MockTransport(handler),
    )
    result = provider.chat("some-model", msg("hi"))
    assert result.text == "answer"
    assert (result.prompt_tokens, result.completion_tokens) == (7, 3)
    assert result.tokens_per_second and result.tokens_per_second > 0


def test_openai_compat_requires_key():
    provider = OpenAICompatProvider("nim", "http://x/v1", requires_key=True)
    assert not provider.is_available()
    with pytest.raises(ProviderError, match="No API key"):
        provider.chat("m", msg("hi"))


def test_openai_compat_bad_payload():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"oops": True}))
    provider = OpenAICompatProvider("llamacpp", "http://x/v1", transport=transport)
    with pytest.raises(ProviderError, match="Unexpected response"):
        provider.chat("m", msg("hi"))
