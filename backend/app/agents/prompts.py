"""Prompt templates. Every prompt starts with a TASK marker line.

Real models ignore the marker. The offline mock provider uses it to know what is being asked.
"""

from __future__ import annotations

import json

REFUSAL_TEXT = "I could not find this in the provided documents."
REJECTED_TEXT = "The answer was rejected because it was not grounded in the provided sources."

DEFAULT_SYSTEM_PROMPT = (
    "You are a careful analyst for a grid equipment company. You answer questions about "
    "win/loss reports and maintenance manuals. You never invent facts."
)

EXTRACTION_SYSTEM_PROMPT = (
    "You extract structured data from business documents. Reply with a single JSON object only."
)

ROUTER_SYSTEM_PROMPT = "You choose the right tool for a question. Reply with a single JSON object."


def build_answer_prompt(question: str, context_blocks: list[str], result_lines: list[str]) -> str:
    context_parts = [f"RESULT: {line}" for line in result_lines] + context_blocks
    context = "\n".join(context_parts) if context_parts else "(no context found)"
    return (
        "TASK:rag_answer\n"
        "Answer the question using ONLY the context below. Cite every statement with the id of "
        "its source in square brackets, written like [doc-id#0]. If the context does not "
        f"contain the answer, reply exactly: {REFUSAL_TEXT}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}"
    )


def build_retry_prompt(original_prompt: str, errors: list[str]) -> str:
    problems = "; ".join(errors)
    return (
        f"{original_prompt}\n\n"
        f"Your previous answer was rejected: {problems}. Answer again. Every statement must "
        "end with a citation like [doc-id#0] that uses only an id from the context."
    )


def build_route_prompt(question: str, competitors: list[str], regions: list[str]) -> str:
    return (
        "TASK:route\n"
        "Choose the tool that answers the question. Reply with JSON only.\n"
        "Tools:\n"
        '- search_documents: {"query": "<search text>"} for questions about one report or '
        "about a maintenance manual.\n"
        '- query_records: {"aggregate": "list" | "count" | "avg_our_price", '
        '"outcome": "won" | "lost" | null, "competitor": <name or null>, '
        '"region": <name or null>} for questions that count, list or average deals.\n'
        f"Competitors: {', '.join(competitors)}\n"
        f"Regions: {', '.join(regions)}\n"
        'Reply like {"tool": "search_documents", "args": {"query": "..."}}.\n'
        f"Question: {question}"
    )


def build_extract_prompt(document_text: str) -> str:
    schema = {
        "customer": "string",
        "region": "string",
        "deal_date": "YYYY-MM-DD",
        "outcome": "won or lost",
        "our_price_eur": "number",
        "competitor": "string",
        "competitor_price_eur": "number",
        "reason_category": "one of price, lead_time, technical, relationship, compliance",
    }
    return (
        "TASK:extract\n"
        "Extract these fields from the win/loss report and reply with JSON only:\n"
        f"{json.dumps(schema)}\n"
        "Prices are plain numbers in EUR (3.9 million is 3900000). reason_category is the "
        "main reason for the outcome. Use null for anything that is not in the report.\n\n"
        f"Report:\n{document_text}"
    )
