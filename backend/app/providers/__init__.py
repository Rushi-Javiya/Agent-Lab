"""Model providers and the factory that creates them from the settings."""

from __future__ import annotations

import httpx

from ..config import Settings
from .base import ChatMessage, ChatResult, LLMProvider, ProviderError
from .mock import MockProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider

PROVIDER_NAMES = ("mock", "ollama", "llamacpp", "nim", "openai")

__all__ = [
    "PROVIDER_NAMES",
    "ChatMessage",
    "ChatResult",
    "LLMProvider",
    "ProviderError",
    "get_provider",
    "provider_status",
]


def get_provider(
    name: str, settings: Settings, transport: httpx.BaseTransport | None = None
) -> LLMProvider:
    timeout = settings.request_timeout_s
    if name == "mock":
        return MockProvider()
    if name == "ollama":
        return OllamaProvider(settings.ollama_url, timeout=timeout, transport=transport)
    if name == "llamacpp":
        return OpenAICompatProvider(
            "llamacpp", settings.llamacpp_url, timeout=timeout, transport=transport
        )
    if name == "nim":
        return OpenAICompatProvider(
            "nim",
            settings.nim_url,
            api_key=settings.nim_api_key,
            requires_key=True,
            timeout=timeout,
            transport=transport,
        )
    if name == "openai":
        return OpenAICompatProvider(
            "openai",
            settings.openai_url,
            api_key=settings.openai_api_key,
            requires_key=True,
            timeout=timeout,
            transport=transport,
        )
    raise ProviderError(f"Unknown provider '{name}'. Use one of {', '.join(PROVIDER_NAMES)}.")


def provider_status(settings: Settings) -> dict[str, dict]:
    """Availability and models for each provider, used by the health endpoint and the UI."""
    status: dict[str, dict] = {}
    for name in PROVIDER_NAMES:
        provider = get_provider(name, settings)
        available = provider.is_available()
        status[name] = {
            "available": available,
            "models": provider.list_models() if available else [],
        }
    return status
