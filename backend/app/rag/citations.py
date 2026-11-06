"""Deterministic grounding validation: an answer must cite sources that were really provided."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..agents.prompts import REFUSAL_TEXT

CITATION_RE = re.compile(r"\[([A-Za-z0-9_\-]+(?:#\d+)?)\]")
_REFUSAL_START = re.compile(r"^\s*(i\s+)?(could\s*not|couldn't|cannot|can't)\s+find\b", re.I)


@dataclass
class ValidationResult:
    valid: bool
    citations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_citations(text: str) -> list[str]:
    """Unique citation ids in order of first appearance."""
    seen: list[str] = []
    for match in CITATION_RE.finditer(text):
        citation = match.group(1)
        if citation not in seen:
            seen.append(citation)
    return seen


def doc_id_of(citation: str) -> str:
    return citation.split("#", 1)[0]


def is_refusal(text: str) -> bool:
    cleaned = text.strip()
    return REFUSAL_TEXT.lower() in cleaned.lower() or bool(_REFUSAL_START.match(cleaned))


def validate_answer(
    answer: str,
    allowed_chunk_ids: set[str],
    allowed_doc_ids: set[str],
    require_citations: bool = True,
) -> ValidationResult:
    """Reject answers without citations or with citations to sources that were not provided."""
    if not answer.strip():
        return ValidationResult(False, [], ["the answer is empty"])
    if is_refusal(answer):
        return ValidationResult(True, [], [])

    citations = extract_citations(answer)
    errors: list[str] = []
    if require_citations and not citations:
        errors.append("the answer has no citations")
    for citation in citations:
        if "#" in citation:
            if citation not in allowed_chunk_ids:
                errors.append(f"[{citation}] is not one of the provided sources")
        elif citation not in allowed_doc_ids:
            errors.append(f"[{citation}] is not one of the provided sources")
    return ValidationResult(not errors, citations, errors)
