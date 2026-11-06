"""Storing and loading the structured win/loss records."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import Database
from ..models import WinLossRecord
from ..rag.corpus import Corpus
from .extraction_rules import extract_with_rules


def upsert_record(session: Session, doc_id: str, data: dict, method: str, model: str = "") -> None:
    record = session.scalar(select(WinLossRecord).where(WinLossRecord.doc_id == doc_id))
    if record is None:
        record = WinLossRecord(doc_id=doc_id)
        session.add(record)
    record.customer = data.get("customer")
    record.region = data.get("region")
    record.deal_date = data.get("deal_date")
    record.outcome = data.get("outcome")
    record.our_price_eur = data.get("our_price_eur")
    record.competitor = data.get("competitor")
    record.competitor_price_eur = data.get("competitor_price_eur")
    record.reason_category = data.get("reason_category")
    record.method = method
    record.model = model


def load_reference_records(db: Database, data_dir: Path) -> int:
    """Seed the records table from the curated reference file.

    The agents answer aggregate questions from this table, so it has to be correct. The
    extraction experiment (rules vs. LLM) is measured against the same file.
    """
    rows = json.loads((Path(data_dir) / "records_truth.json").read_text(encoding="utf-8"))
    with db.session() as session:
        for row in rows:
            upsert_record(session, row["doc_id"], row, "reference")
    return len(rows)


def load_records_with_rules(db: Database, corpus: Corpus) -> int:
    """Overwrite the records table with the rule based extractor (no model needed)."""
    count = 0
    with db.session() as session:
        for doc_id, document in corpus.documents.items():
            if document.kind != "winloss":
                continue
            upsert_record(session, doc_id, extract_with_rules(document.text), "rules")
            count += 1
    return count
