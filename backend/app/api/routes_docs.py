"""Documents, structured records and the extraction experiment."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..agents.extraction import evaluate_extraction, load_truth
from ..agents.records import upsert_record
from ..config import Settings
from ..db import Database
from ..models import WinLossRecord
from ..rag.corpus import Corpus
from .deps import get_corpus, get_db, get_settings
from .schemas import ExtractRequest

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents")
def list_documents(corpus: Corpus = Depends(get_corpus)) -> list[dict]:
    counts: dict[str, int] = {}
    for chunk in corpus.chunks:
        counts[chunk.doc_id] = counts.get(chunk.doc_id, 0) + 1
    return [
        {"doc_id": d.doc_id, "title": d.title, "kind": d.kind, "chunks": counts.get(d.doc_id, 0)}
        for d in corpus.documents.values()
    ]


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, corpus: Corpus = Depends(get_corpus)) -> dict:
    document = corpus.get_document(doc_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    chunks = [{"chunk_id": c.chunk_id, "text": c.text} for c in corpus.chunks if c.doc_id == doc_id]
    return {
        "doc_id": document.doc_id,
        "title": document.title,
        "kind": document.kind,
        "text": document.text,
        "chunks": chunks,
    }


@router.get("/search")
def search(q: str, top_k: int = 4, corpus: Corpus = Depends(get_corpus)) -> list[dict]:
    hits = corpus.search(q, max(1, min(top_k, 12)))
    return [
        {
            "chunk_id": h.chunk.chunk_id,
            "doc_id": h.chunk.doc_id,
            "score": h.score,
            "text": h.chunk.text,
        }
        for h in hits
    ]


@router.get("/records")
def list_records(db: Database = Depends(get_db)) -> list[dict]:
    with db.session() as session:
        rows = session.scalars(select(WinLossRecord).order_by(WinLossRecord.deal_date)).all()
        return [
            {
                "doc_id": r.doc_id,
                "customer": r.customer,
                "region": r.region,
                "deal_date": r.deal_date,
                "outcome": r.outcome,
                "our_price_eur": r.our_price_eur,
                "competitor": r.competitor,
                "competitor_price_eur": r.competitor_price_eur,
                "reason_category": r.reason_category,
                "method": r.method,
                "model": r.model,
            }
            for r in rows
        ]


@router.post("/records/extract")
def extract_records(
    body: ExtractRequest,
    db: Database = Depends(get_db),
    corpus: Corpus = Depends(get_corpus),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Extract the fields from every report and score them against the reference records.

    With `apply` the extracted values replace the rows in the records table, which changes
    what the records tool returns to the agents. Reports that could not be extracted are kept.
    """
    report = evaluate_extraction(
        corpus, load_truth(settings.data_dir), body.method, settings, body.provider, body.model
    )
    applied = 0
    if body.apply:
        with db.session() as session:
            for doc in report["documents"]:
                if doc["extracted"]:
                    label = body.method
                    upsert_record(session, doc["doc_id"], doc["extracted"], label, body.model)
                    applied += 1
    report["applied"] = applied
    return report
