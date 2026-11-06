"""Ollama through its native API, which reports exact generation speed."""

from __future__ import annotations

import time

import httpx

from .base import ChatMessage, ChatResult, ProviderError


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        base_url: str,
        timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, transport=transport
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
        options: dict = {"temperature": temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"

        started = time.perf_counter()
        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise ProviderError(f"Ollama returned {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not reach Ollama: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        data = response.json()
        completion_tokens = int(data.get("eval_count") or 0)
        eval_duration_ns = int(data.get("eval_duration") or 0)
        tokens_per_second = None
        if completion_tokens and eval_duration_ns:
            tokens_per_second = completion_tokens / (eval_duration_ns / 1e9)

        return ChatResult(
            text=(data.get("message") or {}).get("content", ""),
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            tokens_per_second=tokens_per_second,
            model=model,
        )

    def list_models(self) -> list[str]:
        try:
            response = self._client.get("/api/tags", timeout=3.0)
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return [m["name"] for m in response.json().get("models", [])]

    def is_available(self) -> bool:
        try:
            self._client.get("/api/tags", timeout=2.0).raise_for_status()
        except httpx.HTTPError:
            return False
        return True
