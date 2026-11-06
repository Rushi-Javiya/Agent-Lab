"""Common types for all model providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    tokens_per_second: float | None = None
    model: str = ""


class ProviderError(RuntimeError):
    """Raised when a model server is unreachable or returns an error."""


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult: ...

    def list_models(self) -> list[str]: ...

    def is_available(self) -> bool: ...
