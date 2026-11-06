"""Providers that speak the OpenAI chat completions API (llama.cpp server, NVIDIA NIM, OpenAI)."""

from __future__ import annotations

import time

import httpx

from .base import ChatMessage, ChatResult, ProviderError


class OpenAICompatProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str = "",
        requires_key: bool = False,
        timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self._requires_key = requires_key
        self._api_key = api_key
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        if self._requires_key and not self._api_key:
            raise ProviderError(f"No API key configured for provider '{self.name}'")

        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ProviderError(
                f"{self.name} returned {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach {self.name}: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        data = response.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected response from {self.name}: {str(data)[:200]}") from exc
        usage = data.get("usage") or {}
        completion_tokens = int(usage.get("completion_tokens") or 0)

        # The API does not report generation time, so this includes prompt processing.
        tokens_per_second = (
            completion_tokens / (latency_ms / 1000) if completion_tokens and latency_ms else None
        )
        return ChatResult(
            text=text,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            tokens_per_second=tokens_per_second,
            model=model,
        )

    def list_models(self) -> list[str]:
        if self._requires_key and not self._api_key:
            return []
        try:
            response = self._client.get("/models", timeout=3.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return [m["id"] for m in response.json().get("data", [])]

    def is_available(self) -> bool:
        if self._requires_key:
            return bool(self._api_key)
        try:
            self._client.get("/models", timeout=2.0).raise_for_status()
        except httpx.HTTPError:
            return False
        return True
