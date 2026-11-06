"""Housekeeping that runs when the application starts."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from .db import Database
from .models import BenchmarkRun, EvalRun


def mark_interrupted_runs(db: Database) -> int:
    """Runs execute in a background thread. If the server stops, they would stay 'running'."""
    count = 0
    with db.session() as session:
        for model in (EvalRun, BenchmarkRun):
            stmt = select(model).where(model.status.in_(("queued", "running")))
            for run in session.scalars(stmt).all():
                run.status = "failed"
                run.error = "Interrupted by a server restart."
                run.finished_at = datetime.now(UTC)
                count += 1
    return count
