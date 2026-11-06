"""Decide which tool answers a question: document search or a structured records query."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

TOOL_SEARCH = "search_documents"
TOOL_RECORDS = "query_records"

AGGREGATES = ("list", "count", "avg_our_price")

_AGGREGATE_CUES: list[tuple[str, str]] = [
    (r"\bhow many\b", "count"),
    (r"\bnumber of\b", "count"),
    (r"\bcount\b", "count"),
    (r"\baverage\b", "avg_our_price"),
    (r"\bmean\b", "avg_our_price"),
    (r"\blist\b", "list"),
    (r"\bwhich (deals|customers|bids|tenders)\b", "list"),
]

_DOMAIN_TERMS = re.compile(
    r"\b(deal|deals|bid|bids|tender|tenders|customer|customers|price|prices|"
    r"win|wins|won|winning|lost|lose|losing|loss|losses)\b"
)


@dataclass
class Route:
    tool: str
    args: dict = field(default_factory=dict)
    source: str = "heuristic"


def heuristic_route(question: str, competitors: list[str], regions: list[str]) -> Route:
    """Rule based router. Aggregate questions about deals go to the records tool."""
    q = question.lower()
    aggregate = next((agg for pattern, agg in _AGGREGATE_CUES if re.search(pattern, q)), None)
    if aggregate is None or not _DOMAIN_TERMS.search(q):
        return Route(TOOL_SEARCH, {"query": question})

    args: dict = {"aggregate": aggregate}
    if re.search(r"\b(lost|lose|losing|loss|losses)\b", q):
        args["outcome"] = "lost"
    elif re.search(r"\b(won|win|wins|winning)\b", q):
        args["outcome"] = "won"
    for competitor in competitors:
        if competitor.lower() in q:
            args["competitor"] = competitor
    for region in regions:
        if region.lower() in q:
            args["region"] = region
    return Route(TOOL_RECORDS, args)


def parse_route_json(data: dict, fallback_question: str) -> Route | None:
    """Validate the JSON an LLM returned for the routing step. Returns None if unusable."""
    tool = data.get("tool")
    args = data.get("args") or {}
    if not isinstance(args, dict):
        return None
    if tool == TOOL_SEARCH:
        query = args.get("query") or fallback_question
        return Route(TOOL_SEARCH, {"query": str(query)}, source="llm")
    if tool == TOOL_RECORDS:
        clean: dict = {}
        aggregate = args.get("aggregate") or "list"
        if aggregate not in AGGREGATES:
            return None
        clean["aggregate"] = aggregate
        for key in ("outcome", "competitor", "region"):
            value = args.get(key)
            if value:
                clean[key] = str(value)
        if clean.get("outcome") not in (None, "won", "lost"):
            return None
        return Route(TOOL_RECORDS, clean, source="llm")
    return None
