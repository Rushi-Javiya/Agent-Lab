"""The tools an agent can call: document search and a structured records query."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import func, select

from ..db import Database
from ..models import WinLossRecord
from ..rag.corpus import Corpus
from .router import TOOL_RECORDS, TOOL_SEARCH

MAX_ROWS = 20


@dataclass
class ToolOutput:
    name: str
    args: dict
    context_blocks: list[str] = field(default_factory=list)
    result_lines: list[str] = field(default_factory=list)
    allowed_chunk_ids: set[str] = field(default_factory=set)
    allowed_doc_ids: set[str] = field(default_factory=set)
    summary: str = ""
    latency_ms: float = 0.0
    empty: bool = False

    def trace(self) -> dict:
        return {
            "type": "tool",
            "name": self.name,
            "args": self.args,
            "summary": self.summary,
            "latency_ms": round(self.latency_ms, 2),
        }


def _eur(value: float | None) -> str:
    return "n/a" if value is None else f"EUR {value:,.0f}"


class ToolBox:
    def __init__(self, corpus: Corpus, db: Database) -> None:
        self.corpus = corpus
        self.db = db

    def known_values(self) -> tuple[list[str], list[str]]:
        """Competitors and regions that appear in the records, used by the router."""
        with self.db.session() as session:
            competitors = session.scalars(
                select(WinLossRecord.competitor)
                .where(WinLossRecord.competitor.is_not(None))
                .distinct()
                .order_by(WinLossRecord.competitor)
            ).all()
            regions = session.scalars(
                select(WinLossRecord.region)
                .where(WinLossRecord.region.is_not(None))
                .distinct()
                .order_by(WinLossRecord.region)
            ).all()
        return list(competitors), list(regions)

    def run(self, name: str, args: dict, top_k: int) -> ToolOutput:
        if name == TOOL_SEARCH:
            return self.search_documents(str(args.get("query", "")), top_k)
        if name == TOOL_RECORDS:
            return self.query_records(
                aggregate=args.get("aggregate", "list"),
                outcome=args.get("outcome"),
                competitor=args.get("competitor"),
                region=args.get("region"),
            )
        raise ValueError(f"Unknown tool '{name}'")

    def search_documents(self, query: str, top_k: int = 4) -> ToolOutput:
        started = time.perf_counter()
        hits = self.corpus.search(query, top_k)
        output = ToolOutput(TOOL_SEARCH, {"query": query, "top_k": top_k}, empty=not hits)
        for hit in hits:
            chunk = hit.chunk
            output.context_blocks.append(f"[{chunk.chunk_id}]\n{chunk.text}")
            output.allowed_chunk_ids.add(chunk.chunk_id)
            output.allowed_doc_ids.add(chunk.doc_id)
        output.summary = f"{len(hits)} chunks: " + ", ".join(
            f"{h.chunk.chunk_id} ({h.score:.2f})" for h in hits
        )
        output.latency_ms = (time.perf_counter() - started) * 1000
        return output

    def query_records(
        self,
        aggregate: str = "list",
        outcome: str | None = None,
        competitor: str | None = None,
        region: str | None = None,
    ) -> ToolOutput:
        started = time.perf_counter()
        args = {
            k: v
            for k, v in {
                "aggregate": aggregate,
                "outcome": outcome,
                "competitor": competitor,
                "region": region,
            }.items()
            if v
        }
        stmt = select(WinLossRecord).order_by(WinLossRecord.deal_date)
        if outcome:
            stmt = stmt.where(func.lower(WinLossRecord.outcome) == outcome.lower())
        if competitor:
            stmt = stmt.where(func.lower(WinLossRecord.competitor) == competitor.lower())
        if region:
            stmt = stmt.where(func.lower(WinLossRecord.region) == region.lower())
        with self.db.session() as session:
            rows = list(session.scalars(stmt).all())

        output = ToolOutput(TOOL_RECORDS, args, empty=not rows)
        if aggregate == "count":
            output.result_lines.append(f"count={len(rows)}")
        elif aggregate == "avg_our_price":
            prices = [r.our_price_eur for r in rows if r.our_price_eur is not None]
            average = sum(prices) / len(prices) if prices else 0
            output.result_lines.append(f"avg_our_price={average:.0f}")
        else:
            output.result_lines.append(f"list={len(rows)}")

        for row in rows[:MAX_ROWS]:
            output.context_blocks.append(
                f"[{row.doc_id}] Customer: {row.customer} | region: {row.region} | "
                f"date: {row.deal_date} | outcome: {row.outcome} | "
                f"our price: {_eur(row.our_price_eur)} | competitor: {row.competitor} | "
                f"competitor price: {_eur(row.competitor_price_eur)} | reason: {row.reason_category}"
            )
            output.allowed_doc_ids.add(row.doc_id)
        output.summary = f"{len(rows)} records; {output.result_lines[0]}"
        output.latency_ms = (time.perf_counter() - started) * 1000
        return output
