"""Seed the database with the reference records, the datasets and two demo agent versions."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from .agents.rag_agent import AgentConfig
from .agents.records import load_reference_records
from .agents.registry import add_version, create_agent
from .db import Database
from .evals.datasets import sync_datasets
from .models import Agent

DEMO_SLUG = "winloss-rag"


def seed_all(db: Database, data_dir: Path) -> dict:
    """Idempotent: running it twice does not create duplicates."""
    records = load_reference_records(db, data_dir)
    datasets = sync_datasets(db, data_dir)

    created_agent = False
    with db.session() as session:
        agent = session.scalar(select(Agent).where(Agent.slug == DEMO_SLUG))
        if agent is None:
            agent = create_agent(
                session,
                DEMO_SLUG,
                "Win/loss RAG assistant",
                "Answers questions about win/loss reports and maintenance manuals with "
                "citations. Uses document search and a SQL records tool.",
                AgentConfig(provider="mock", model="mock-extractive"),
                note="Baseline with the offline mock model.",
            )
            add_version(
                session,
                agent,
                AgentConfig(provider="mock", model="mock-sloppy"),
                note="Deliberately weak mock model, to show how regressions are detected.",
            )
            created_agent = True
    return {"records": records, "datasets": datasets, "demo_agent_created": created_agent}
