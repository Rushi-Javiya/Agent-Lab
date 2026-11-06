"""Structured extraction from win/loss reports with a model or with rules, scored against truth."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import Settings
from ..providers import ChatMessage, ProviderError, get_provider
from ..rag.corpus import Corpus
from .extraction_rules import FIELDS, REASON_CATEGORIES, extract_with_rules, parse_number
from .jsonutil import parse_json_object
from .prompts import EXTRACTION_SYSTEM_PROMPT, build_extract_prompt

STRING_FIELDS = ("customer", "region", "outcome", "competitor", "reason_category")
PRICE_FIELDS = ("our_price_eur", "competitor_price_eur")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _to_price(value) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).lower().replace("eur", "").replace("€", "").strip()
    multiplier = 1.0
    if "million" in text or text.endswith("m"):
        multiplier = 1e6
        text = text.replace("million", "").rstrip("m").strip()
    number = parse_number(text)
    return None if number is None else number * multiplier


def clean_extraction(data: dict) -> dict | None:
    """Validate and normalise what a model returned. Returns None if it is unusable."""
    cleaned: dict = dict.fromkeys(FIELDS)
    for name in ("customer", "region", "competitor"):
        value = data.get(name)
        cleaned[name] = str(value).strip() if value not in (None, "", "null") else None

    outcome = str(data.get("outcome") or "").strip().lower()
    cleaned["outcome"] = outcome if outcome in ("won", "lost") else None

    date = str(data.get("deal_date") or "").strip()
    cleaned["deal_date"] = date if _DATE_RE.match(date) else None

    for name in PRICE_FIELDS:
        cleaned[name] = _to_price(data.get(name))

    reason = str(data.get("reason_category") or "").strip().lower().replace(" ", "_")
    cleaned["reason_category"] = reason if reason in REASON_CATEGORIES else None

    if cleaned["outcome"] is None and cleaned["customer"] is None:
        return None
    return cleaned


def extract_with_llm(
    settings: Settings, provider_name: str, model: str, text: str, retries: int = 1
) -> dict | None:
    provider = get_provider(provider_name, settings)
    prompt = build_extract_prompt(text)
    for _ in range(retries + 1):
        reply = provider.chat(
            model,
            [ChatMessage("system", EXTRACTION_SYSTEM_PROMPT), ChatMessage("user", prompt)],
            temperature=0.0,
            json_mode=True,
        )
        data = parse_json_object(reply.text)
        cleaned = clean_extraction(data) if data else None
        if cleaned is not None:
            return cleaned
    return None


def _same(field: str, expected, got) -> bool:
    if got is None:
        return False
    if field in PRICE_FIELDS:
        return abs(float(expected) - float(got)) <= abs(float(expected)) * 0.005
    return str(expected).strip().casefold() == str(got).strip().casefold()


def load_truth(data_dir: Path) -> list[dict]:
    return json.loads((Path(data_dir) / "records_truth.json").read_text(encoding="utf-8"))


def evaluate_extraction(
    corpus: Corpus,
    truth: list[dict],
    method: str,
    settings: Settings,
    provider: str = "mock",
    model: str = "mock-extractive",
) -> dict:
    """Extract every report and compare each field with the reference records."""
    documents = []
    correct_by_field = dict.fromkeys(FIELDS, 0)

    for row in truth:
        document = corpus.get_document(row["doc_id"])
        entry: dict = {"doc_id": row["doc_id"], "extracted": None, "fields": {}, "error": None}
        try:
            if method == "llm":
                extracted = extract_with_llm(settings, provider, model, document.text)
            else:
                extracted = extract_with_rules(document.text)
        except ProviderError as exc:
            extracted = None
            entry["error"] = str(exc)
        entry["extracted"] = extracted

        for field in FIELDS:
            got = (extracted or {}).get(field)
            ok = _same(field, row[field], got)
            correct_by_field[field] += int(ok)
            entry["fields"][field] = {"expected": row[field], "got": got, "correct": ok}
        documents.append(entry)

    total = len(truth) or 1
    field_accuracy = {f: round(correct_by_field[f] / total, 4) for f in FIELDS}
    return {
        "method": method,
        "provider": provider if method == "llm" else None,
        "model": model if method == "llm" else None,
        "documents": documents,
        "field_accuracy": field_accuracy,
        "overall_accuracy": round(sum(field_accuracy.values()) / len(FIELDS), 4),
    }
