"""Deterministic metrics for question answering agents. No model is used to judge answers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..agents.rag_agent import AgentResult
from ..rag.citations import doc_id_of

PASS_THRESHOLD = 0.7
WEIGHTS = {"fact_coverage": 0.4, "citation_valid": 0.2, "citation_recall": 0.2, "tool_correct": 0.2}

_NUMBER_RE = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)(?:\s*(million|billion|thousand|bn|m|k)\b)?", re.I
)
_PURE_NUMBER_RE = re.compile(
    r"(?:eur\s*)?[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|thousand|bn|m|k))?", re.I
)
_MULTIPLIERS = {"million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "thousand": 1e3, "k": 1e3}


def extract_numbers(text: str) -> set[float]:
    """All numbers in a text. '4.6 million', 'EUR 4.6M' and '4,600,000' give the same value."""
    numbers: set[float] = set()
    for match in _NUMBER_RE.finditer(text):
        raw = match.group(1).replace(",", "").rstrip(".")
        try:
            value = float(raw)
        except ValueError:
            continue
        unit = (match.group(2) or "").lower()
        numbers.add(round(value * _MULTIPLIERS.get(unit, 1.0), 6))
    return numbers


def _normalize(text: str) -> str:
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def fact_matches(fact: str, answer: str) -> bool:
    """A numeric fact matches by value, any other fact matches as a case-insensitive phrase."""
    fact = fact.strip()
    if _PURE_NUMBER_RE.fullmatch(fact):
        wanted = extract_numbers(fact.lower().replace("eur", ""))
        if wanted:
            found = extract_numbers(answer)
            return all(any(abs(w - f) <= max(1e-6, abs(w) * 1e-9) for f in found) for w in wanted)
    return _normalize(fact) in _normalize(answer)


def fact_coverage(expected_facts: list[str], answer: str) -> float:
    if not expected_facts:
        return 1.0
    hits = sum(1 for fact in expected_facts if fact_matches(fact, answer))
    return hits / len(expected_facts)


def citation_recall(expected_docs: list[str], citations: list[str]) -> float:
    if not expected_docs:
        return 1.0
    cited = {doc_id_of(c) for c in citations}
    return sum(1 for doc in expected_docs if doc in cited) / len(expected_docs)


def retrieval_recall(expected_docs: list[str], tool_calls: list[dict]) -> float:
    """Did the tools bring the expected documents into the context at all?"""
    if not expected_docs:
        return 1.0
    retrieved: set[str] = set()
    for call in tool_calls:
        if call.get("type") == "tool":
            retrieved.update(doc_id_of(item) for item in call.get("retrieved", []))
    return sum(1 for doc in expected_docs if doc in retrieved) / len(expected_docs)


def tool_correct(expected_tools: list[str], used_tools: list[str]) -> float:
    if not expected_tools:
        return 1.0
    return 1.0 if all(tool in used_tools for tool in expected_tools) else 0.0


@dataclass
class CaseScore:
    metrics: dict
    score: float
    passed: bool


def score_case(case: dict, result: AgentResult) -> CaseScore:
    threshold = float(case.get("pass_threshold", PASS_THRESHOLD))

    if result.status == "error":
        return CaseScore({"error": 1.0}, 0.0, False)

    if case.get("should_refuse"):
        correct = {"refused": 1.0, "rejected": 0.5}.get(result.status, 0.0)
        return CaseScore({"refusal_correct": correct}, correct, correct >= 1.0)

    metrics = {
        "fact_coverage": fact_coverage(case.get("expected_facts", []), result.answer),
        "citation_valid": 1.0 if result.status == "answered" and result.citations else 0.0,
        "citation_recall": citation_recall(case.get("expected_docs", []), result.citations),
        "tool_correct": tool_correct(case.get("expected_tools", []), result.tools_used),
        "retrieval_recall": retrieval_recall(case.get("expected_docs", []), result.tool_calls),
    }
    score = sum(metrics[name] * weight for name, weight in WEIGHTS.items())
    passed = score >= threshold and result.status == "answered"
    return CaseScore(metrics, round(score, 4), passed)
