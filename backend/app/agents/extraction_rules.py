"""Rule based extraction of structured fields from a win/loss report.

It reads the header block of the structured reports and falls back to a few patterns for the
narrative ones. The LLM extractor is compared against it, so it doubles as a baseline.
"""

from __future__ import annotations

import re

REASON_CATEGORIES = ("price", "lead_time", "technical", "relationship", "compliance")

FIELDS = (
    "customer",
    "region",
    "deal_date",
    "outcome",
    "our_price_eur",
    "competitor",
    "competitor_price_eur",
    "reason_category",
)

_HEADER_PATTERNS = {
    "customer": r"^Customer:\s*(.+?)\s*$",
    "region": r"^Region:\s*(.+?)\s*$",
    "deal_date": r"^Date:\s*(\d{4}-\d{2}-\d{2})\s*$",
    "outcome": r"^Outcome:\s*(won|lost)\s*$",
    "our_price_eur": r"^Our price:\s*EUR\s*([\d,\.]+)\s*$",
    "competitor": r"^Competitor:\s*(.+?)\s*$",
    "competitor_price_eur": r"^Competitor price:\s*EUR\s*([\d,\.]+)\s*$",
}

# (keyword regex, weight) per reason category. Sentences with a negation are ignored.
_REASON_KEYWORDS: dict[str, list[tuple[str, int]]] = {
    "price": [(r"\bprice\b", 1), (r"\bcheaper\b", 1), (r"\bbid\b", 1), (r"\bgap\b", 1)],
    "lead_time": [(r"\bdelivery\b", 2), (r"\bweeks\b", 1), (r"\bslot\b", 1), (r"\bschedule\b", 1)],
    "technical": [
        (r"\bdesign\b", 1),
        (r"\bsimulation\b", 1),
        (r"\blosses\b", 1),
        (r"\bloss\b", 1),
        (r"\bmonitoring\b", 1),
        (r"\btechnical\b", 1),
        (r"\bharmonic\b", 1),
    ],
    "relationship": [
        (r"\bservice team\b", 2),
        (r"\btrust\b", 2),
        (r"\bframework agreement\b", 2),
        (r"\blocal\b", 1),
    ],
    "compliance": [(r"\bcertification\b", 3), (r"\bcertified\b", 2)],
}

_NEGATION = re.compile(r"\b(not|no|did not|never)\s")


def parse_number(raw: str) -> float | None:
    cleaned = raw.replace(",", "").strip().rstrip(".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _reason_section(text: str) -> str:
    match = re.search(r"##\s*Why we (?:won|lost)\s*\n(.+?)(?=\n##|\Z)", text, re.S | re.I)
    return match.group(1) if match else text


def classify_reason(text: str) -> str | None:
    section = _reason_section(text)
    sentences = re.split(r"(?<=[.!?])\s+", section.replace("\n", " "))
    scores = dict.fromkeys(REASON_CATEGORIES, 0)
    for sentence in sentences:
        lowered = sentence.lower()
        if _NEGATION.search(lowered + " "):
            continue
        for category, keywords in _REASON_KEYWORDS.items():
            for pattern, weight in keywords:
                scores[category] += weight * len(re.findall(pattern, lowered))
    best = max(scores.items(), key=lambda item: item[1])
    return best[0] if best[1] > 0 else None


def extract_with_rules(text: str) -> dict:
    """Return a dict with all FIELDS. Missing values are None."""
    result: dict = dict.fromkeys(FIELDS)

    title = re.search(r"^#\s*Win/Loss Report:\s*(.+?)\s*$", text, re.M)
    if title:
        result["customer"] = title.group(1)

    for field_name, pattern in _HEADER_PATTERNS.items():
        match = re.search(pattern, text, re.M | re.I)
        if not match:
            continue
        value = match.group(1).strip()
        if field_name in ("our_price_eur", "competitor_price_eur"):
            result[field_name] = parse_number(value)
        elif field_name == "outcome":
            result[field_name] = value.lower()
        else:
            result[field_name] = value

    if result["outcome"] is None:
        narrative = re.search(r"\bWe (won|lost)\b", text)
        if narrative:
            result["outcome"] = narrative.group(1)

    if result["outcome"] is not None:
        result["reason_category"] = classify_reason(text)
    return result
