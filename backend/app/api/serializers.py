"""Turn database rows into JSON friendly dictionaries."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    Agent,
    AgentRun,
    AgentVersion,
    BenchmarkRun,
    EvalDataset,
    EvalRun,
)


def iso(value: datetime | None) -> str | None:
    """SQLite drops the timezone. All stored times are UTC, so say so explicitly."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def latest_eval(session: Session, version_id: int) -> dict | None:
    run = session.scalar(
        select(EvalRun)
        .where(EvalRun.agent_version_id == version_id, EvalRun.status == "completed")
        .order_by(EvalRun.id.desc())
        .limit(1)
    )
    if run is None:
        return None
    dataset = session.get(EvalDataset, run.dataset_id)
    return {
        "run_id": run.id,
        "dataset": dataset.slug,
        "mean_score": run.summary.get("mean_score"),
        "pass_rate": run.summary.get("pass_rate"),
    }


def version_out(session: Session, version: AgentVersion) -> dict:
    return {
        "id": version.id,
        "version": version.version,
        "config": version.config,
        "note": version.note,
        "created_at": iso(version.created_at),
        "latest_eval": latest_eval(session, version.id),
    }


def agent_summary(session: Session, agent: Agent) -> dict:
    latest = agent.versions[-1] if agent.versions else None
    return {
        "id": agent.id,
        "slug": agent.slug,
        "name": agent.name,
        "description": agent.description,
        "kind": agent.kind,
        "created_at": iso(agent.created_at),
        "version_count": len(agent.versions),
        "latest_version": version_out(session, latest) if latest else None,
    }


def agent_detail(session: Session, agent: Agent) -> dict:
    out = agent_summary(session, agent)
    out["versions"] = [version_out(session, v) for v in agent.versions]
    return out


def run_out(run: AgentRun, version_number: int | None = None) -> dict:
    return {
        "id": run.id,
        "agent_version_id": run.agent_version_id,
        "version": version_number,
        "question": run.question,
        "answer": run.answer,
        "raw_answer": run.raw_answer,
        "status": run.status,
        "citations": run.citations,
        "tool_calls": run.tool_calls,
        "validation_errors": run.validation_errors,
        "latency_ms": round(run.latency_ms, 1),
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "llm_calls": run.llm_calls,
        "error": run.error,
        "created_at": iso(run.created_at),
    }


def eval_run_out(session: Session, run: EvalRun, include_results: bool = False) -> dict:
    version = session.get(AgentVersion, run.agent_version_id)
    agent = session.get(Agent, version.agent_id)
    dataset = session.get(EvalDataset, run.dataset_id)
    out = {
        "id": run.id,
        "status": run.status,
        "agent": {"id": agent.id, "slug": agent.slug, "name": agent.name},
        "version": version.version,
        "config": version.config,
        "dataset": {"id": dataset.id, "slug": dataset.slug, "name": dataset.name},
        "progress": {"done": run.progress_done, "total": run.progress_total},
        "summary": run.summary,
        "error": run.error,
        "created_at": iso(run.created_at),
        "finished_at": iso(run.finished_at),
    }
    if include_results:
        out["results"] = [
            {
                "case_id": r.case_id,
                "question": r.question,
                "answer": r.answer,
                "status": r.status,
                "metrics": r.metrics,
                "score": r.score,
                "passed": r.passed,
                "latency_ms": r.latency_ms,
                "tokens": r.tokens,
                "tool_calls": r.tool_calls,
                "error": r.error,
            }
            for r in run.results
        ]
    return out


def benchmark_out(run: BenchmarkRun) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "prompt_set": run.prompt_set,
        "repeats": run.repeats,
        "progress": {"done": run.progress_done, "total": run.progress_total},
        "error": run.error,
        "created_at": iso(run.created_at),
        "finished_at": iso(run.finished_at),
        "results": [
            {
                "id": r.id,
                "provider": r.provider,
                "model": r.model,
                "stats": r.stats,
                "error": r.error,
            }
            for r in run.results
        ],
    }
