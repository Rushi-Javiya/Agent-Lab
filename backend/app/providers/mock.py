"""An offline test double that follows the prompts of this project.

It is not a language model. `mock-extractive` copies the best matching sentences from the context
with their citations. `mock-sloppy` does the same but misbehaves on purpose in a deterministic
way (missing citations, wrong numbers, made-up answers), which is what the evaluation harness
should catch. Both let tests, CI and demos run without a model server.
"""

from __future__ import annotations

import json
import math
import re
import time
import zlib

from ..agents.extraction_rules import extract_with_rules
from ..agents.prompts import REFUSAL_TEXT
from ..agents.router import heuristic_route
from ..rag.bm25 import tokenize
from .base import ChatMessage, ChatResult, ProviderError

MOCK_MODELS = ["mock-extractive", "mock-sloppy"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _task(prompt: str) -> str:
    match = re.search(r"^TASK:(\w+)", prompt, re.M)
    return match.group(1) if match else "chat"


def _parse_context(prompt: str) -> tuple[list[tuple[str, str]], list[str]]:
    match = re.search(r"Context:\n(.*)\n\nQuestion:", prompt, re.S)
    context = match.group(1) if match else ""
    parts = re.split(r"^\[([^\]\s]+)\]\s*", context, flags=re.M)
    items = [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]
    results = re.findall(r"^RESULT:\s*(.+)$", context, re.M)
    return items, results


def _flatten(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[#*]+", " ", text)).strip()


def _corrupt_numbers(text: str) -> str:
    def bump(match: re.Match) -> str:
        value = match.group(0)
        last = value[-1]
        return value[:-1] + (str((int(last) + 1) % 10) if last.isdigit() else last)

    return re.sub(r"\d[\d,\.]*\d|\d", bump, text)


def _records_answer(items: list[tuple[str, str]], results: list[str]) -> str:
    result = results[0]
    rows = [(doc_id, text) for doc_id, text in items if "#" not in doc_id]
    citations = " ".join(f"[{doc_id}]" for doc_id, _ in rows)

    if result.startswith("count="):
        count = int(result.split("=", 1)[1])
        if count == 0:
            return "No matching deals were found in the records."
        return f"There are {count} matching deals. {citations}"
    if result.startswith("avg_our_price="):
        value = float(result.split("=", 1)[1])
        return f"The average price of our offers is EUR {value:,.0f}. {citations}"
    if not rows:
        return "No matching deals were found in the records."
    names = []
    for doc_id, text in rows:
        customer = re.search(r"Customer:\s*([^|]+)", text)
        names.append(f"{customer.group(1).strip() if customer else doc_id} [{doc_id}]")
    return "Matching deals: " + ", ".join(names) + "."


def _text_answer(question: str, items: list[tuple[str, str]], sloppy: bool, seed: int) -> str:
    context_text = " ".join(text for _, text in items).lower()

    words = re.findall(r"[A-Za-z][A-Za-z0-9]+", question)
    entities = [w for w in words[1:] if w[0].isupper()]
    if not items or any(entity.lower() not in context_text for entity in entities):
        return _unanswerable(items, sloppy, seed)

    question_tokens = set(tokenize(question))
    scored: list[tuple[int, int, str, str]] = []
    order = 0
    for doc_id, text in items:
        for sentence in _SENTENCE_SPLIT.split(_flatten(text)):
            overlap = len(question_tokens & set(tokenize(sentence)))
            scored.append((overlap, -order, sentence, doc_id))
            order += 1

    threshold = max(2, math.ceil(0.5 * len(question_tokens)))
    best = [s for s in sorted(scored, reverse=True) if s[0] >= threshold][:2]
    if not best:
        return _unanswerable(items, sloppy, seed)

    answer = " ".join(f"{sentence} [{doc_id}]" for _, _, sentence, doc_id in best)
    if sloppy:
        mode = seed % 5
        if mode in (0, 1):
            answer = re.sub(r"\s*\[[^\]]+\]", "", answer)
        elif mode == 2:
            answer = _corrupt_numbers(answer)
    return answer


def _unanswerable(items: list[tuple[str, str]], sloppy: bool, seed: int) -> str:
    if sloppy and items and seed % 2 == 0:
        doc_id, text = items[0]
        first = _SENTENCE_SPLIT.split(_flatten(text))[0]
        return f"According to the report, {first} [{doc_id}]"
    return REFUSAL_TEXT


def _route(prompt: str) -> str:
    question = re.search(r"^Question:\s*(.+)$", prompt, re.M)
    competitors = re.search(r"^Competitors:\s*(.*)$", prompt, re.M)
    regions = re.search(r"^Regions:\s*(.*)$", prompt, re.M)

    def split(match: re.Match | None) -> list[str]:
        return [v.strip() for v in match.group(1).split(",") if v.strip()] if match else []

    route = heuristic_route(
        question.group(1) if question else "", split(competitors), split(regions)
    )
    return json.dumps({"tool": route.tool, "args": route.args})


def _extract(prompt: str, sloppy: bool) -> str:
    text = prompt.split("Report:\n", 1)[-1]
    data = extract_with_rules(text)
    if sloppy:
        data["our_price_eur"] = None
        data["reason_category"] = None
    return json.dumps(data)


class MockProvider:
    name = "mock"

    def list_models(self) -> list[str]:
        return list(MOCK_MODELS)

    def is_available(self) -> bool:
        return True

    def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> ChatResult:
        if model not in MOCK_MODELS:
            raise ProviderError(f"Unknown mock model '{model}'. Use one of {MOCK_MODELS}.")

        started = time.perf_counter()
        prompt = "\n".join(m.content for m in messages)
        sloppy = model == "mock-sloppy"
        seed = zlib.crc32(prompt.encode("utf-8"))
        task = _task(prompt)

        if task == "rag_answer":
            items, results = _parse_context(prompt)
            question = re.search(r"^Question:\s*(.+)$", prompt, re.M)
            if results:
                text = _records_answer(items, results)
            else:
                text = _text_answer(question.group(1) if question else "", items, sloppy, seed)
        elif task == "route":
            text = _route(prompt)
        elif task == "extract":
            text = _extract(prompt, sloppy)
        else:
            text = "Mock response: " + " ".join(prompt.split()[:20])

        return ChatResult(
            text=text,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(text.split()),
            latency_ms=(time.perf_counter() - started) * 1000,
            tokens_per_second=None,
            model=model,
        )
