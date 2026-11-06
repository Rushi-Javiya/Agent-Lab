"""The RAG agent: route the question, call a tool, answer with citations, validate the answer."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from ..config import Settings
from ..providers import ChatMessage, ProviderError, get_provider
from ..rag.citations import is_refusal, validate_answer
from .jsonutil import parse_json_object
from .prompts import (
    DEFAULT_SYSTEM_PROMPT,
    REFUSAL_TEXT,
    REJECTED_TEXT,
    ROUTER_SYSTEM_PROMPT,
    build_answer_prompt,
    build_retry_prompt,
    build_route_prompt,
)
from .router import TOOL_RECORDS, Route, heuristic_route, parse_route_json
from .tools import ToolBox

NO_RECORDS_TEXT = "No matching deals were found in the records."


class AgentConfig(BaseModel):
    """Everything that defines the behaviour of one agent version."""

    provider: str = "mock"
    model: str = "mock-extractive"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    top_k: int = Field(4, ge=1, le=12)
    max_retries: int = Field(1, ge=0, le=3)
    router: Literal["heuristic", "llm"] = "heuristic"
    require_citations: bool = True
    max_tokens: int | None = Field(None, ge=16, le=4096)


@dataclass
class AgentResult:
    question: str
    answer: str = ""
    raw_answer: str = ""
    status: str = "answered"  # answered | refused | rejected | error
    citations: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    error: str | None = None

    @property
    def tools_used(self) -> list[str]:
        return [c["name"] for c in self.tool_calls if c.get("type") == "tool"]


class RagAgent:
    def __init__(self, config: AgentConfig, toolbox: ToolBox, settings: Settings) -> None:
        self.config = config
        self.toolbox = toolbox
        self.provider = get_provider(config.provider, settings)

    # -- model access -------------------------------------------------------------------

    def _chat(self, result: AgentResult, system: str, prompt: str, json_mode: bool = False) -> str:
        reply = self.provider.chat(
            self.config.model,
            [ChatMessage("system", system), ChatMessage("user", prompt)],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            json_mode=json_mode,
        )
        result.llm_calls += 1
        result.prompt_tokens += reply.prompt_tokens
        result.completion_tokens += reply.completion_tokens
        return reply.text

    # -- steps --------------------------------------------------------------------------

    def _route(self, question: str, result: AgentResult) -> Route:
        competitors, regions = self.toolbox.known_values()
        route = heuristic_route(question, competitors, regions)
        source = "heuristic"
        if self.config.router == "llm":
            prompt = build_route_prompt(question, competitors, regions)
            reply = self._chat(result, ROUTER_SYSTEM_PROMPT, prompt, json_mode=True)
            data = parse_json_object(reply)
            parsed = parse_route_json(data, question) if data else None
            if parsed is not None:
                route, source = parsed, "llm"
            else:
                source = "heuristic_fallback"
        result.tool_calls.append(
            {"type": "route", "source": source, "tool": route.tool, "args": route.args}
        )
        return route

    def run(self, question: str) -> AgentResult:
        started = time.perf_counter()
        result = AgentResult(question=question)
        try:
            self._run(question, result)
        except ProviderError as exc:
            result.status = "error"
            result.error = str(exc)
        result.latency_ms = (time.perf_counter() - started) * 1000
        return result

    def _run(self, question: str, result: AgentResult) -> None:
        cfg = self.config
        route = self._route(question, result)
        output = self.toolbox.run(route.tool, route.args, cfg.top_k)
        result.tool_calls.append(output.trace())

        if output.empty:
            # Nothing was retrieved, so there is nothing to ground an answer on.
            result.status = "answered" if route.tool == TOOL_RECORDS else "refused"
            result.answer = NO_RECORDS_TEXT if route.tool == TOOL_RECORDS else REFUSAL_TEXT
            result.raw_answer = result.answer
            return

        prompt = build_answer_prompt(question, output.context_blocks, output.result_lines)
        raw = self._chat(result, cfg.system_prompt, prompt)
        validation = validate_answer(
            raw, output.allowed_chunk_ids, output.allowed_doc_ids, cfg.require_citations
        )
        retries = 0
        while not validation.valid and retries < cfg.max_retries:
            retries += 1
            result.tool_calls.append(
                {"type": "retry", "reason": validation.errors, "attempt": retries}
            )
            raw = self._chat(
                result, cfg.system_prompt, build_retry_prompt(prompt, validation.errors)
            )
            validation = validate_answer(
                raw, output.allowed_chunk_ids, output.allowed_doc_ids, cfg.require_citations
            )

        result.raw_answer = raw.strip()
        result.validation_errors = validation.errors
        if validation.valid:
            result.status = "refused" if is_refusal(raw) else "answered"
            result.answer = result.raw_answer
            result.citations = validation.citations
        else:
            result.status = "rejected"
            result.answer = REJECTED_TEXT
