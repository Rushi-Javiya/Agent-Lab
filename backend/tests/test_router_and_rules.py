from __future__ import annotations

import json

import pytest

from app.agents.extraction_rules import extract_with_rules
from app.agents.router import TOOL_RECORDS, TOOL_SEARCH, heuristic_route, parse_route_json

COMPETITORS = ["VoltEdge", "GridCore", "Altrix", "NordSwitch"]
REGIONS = ["Central Europe", "Northern Europe", "Asia Pacific"]


@pytest.mark.parametrize(
    ("question", "tool", "args"),
    [
        ("Why did we lose the Nordgrid Utilities deal?", TOOL_SEARCH, None),
        ("How often should transformer oil be sampled?", TOOL_SEARCH, None),
        ("How many months pass between oil samples?", TOOL_SEARCH, None),
        ("How many deals did we lose?", TOOL_RECORDS, {"aggregate": "count", "outcome": "lost"}),
        (
            "How many deals did we win against Altrix?",
            TOOL_RECORDS,
            {"aggregate": "count", "outcome": "won", "competitor": "Altrix"},
        ),
        (
            "What is our average price on lost deals?",
            TOOL_RECORDS,
            {"aggregate": "avg_our_price", "outcome": "lost"},
        ),
        (
            "List the deals we won in Central Europe",
            TOOL_RECORDS,
            {"aggregate": "list", "outcome": "won", "region": "Central Europe"},
        ),
        (
            "Which deals did we lose to VoltEdge?",
            TOOL_RECORDS,
            {"aggregate": "list", "outcome": "lost", "competitor": "VoltEdge"},
        ),
    ],
)
def test_heuristic_route(question, tool, args):
    route = heuristic_route(question, COMPETITORS, REGIONS)
    assert route.tool == tool
    if args is not None:
        assert route.args == args
    else:
        assert route.args == {"query": question}


def test_parse_route_json_accepts_valid_and_rejects_invalid():
    ok = parse_route_json(
        {"tool": "query_records", "args": {"aggregate": "count", "outcome": "won"}}, "q"
    )
    assert ok and ok.args == {"aggregate": "count", "outcome": "won"} and ok.source == "llm"

    assert parse_route_json({"tool": "query_records", "args": {"aggregate": "sum"}}, "q") is None
    assert parse_route_json({"tool": "query_records", "args": {"outcome": "draw"}}, "q") is None
    assert parse_route_json({"tool": "delete_everything", "args": {}}, "q") is None
    search = parse_route_json({"tool": "search_documents", "args": {}}, "my question")
    assert search and search.args == {"query": "my question"}


def test_rules_extract_structured_report(data_dir):
    text = (data_dir / "docs" / "wl-001-nordgrid.md").read_text(encoding="utf-8")
    record = extract_with_rules(text)
    assert record["customer"] == "Nordgrid Utilities"
    assert record["outcome"] == "lost"
    assert record["our_price_eur"] == 4_200_000
    assert record["competitor"] == "VoltEdge"
    assert record["competitor_price_eur"] == 3_850_000
    assert record["reason_category"] == "price"


def test_rules_only_partly_extract_narrative_report(data_dir):
    text = (data_dir / "docs" / "wl-009-tasman.md").read_text(encoding="utf-8")
    record = extract_with_rules(text)
    assert record["customer"] == "Tasman Networks"
    assert record["outcome"] == "lost"
    assert record["our_price_eur"] is None
    assert record["competitor"] is None


def test_rules_reason_classification_on_structured_reports(data_dir):
    truth = json.loads((data_dir / "records_truth.json").read_text(encoding="utf-8"))
    for row in truth[:8]:
        text = (data_dir / "docs" / f"{row['doc_id']}.md").read_text(encoding="utf-8")
        assert extract_with_rules(text)["reason_category"] == row["reason_category"], row["doc_id"]
