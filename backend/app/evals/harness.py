"""Run an agent version against a dataset, store the results and summarise them."""

from __future__ import annotations

import statistics
from collections.abc import Callable
from datetime import UTC, datetime

from ..agents.rag_agent import AgentConfig, RagAgent
from ..agents.tools import ToolBox
from ..config import Settings
from ..db import Database
from ..models import AgentVersion, EvalDataset, EvalResult, EvalRun
from ..rag.corpus import Corpus
from .metrics import score_case


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(results: list[dict]) -> dict:
    """Aggregate the per-case results of one run."""
    if not results:
        return {"cases": 0, "mean_score": 0.0, "pass_rate": 0.0}

    latencies = [r["latency_ms"] for r in results]
    metric_names = sorted({name for r in results for name in r["metrics"]})
    metric_means = {}
    for name in metric_names:
        values = [r["metrics"][name] for r in results if name in r["metrics"]]
        metric_means[name] = round(statistics.fmean(values), 4)

    statuses: dict[str, int] = {}
    for r in results:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1

    return {
        "cases": len(results),
        "mean_score": round(statistics.fmean(r["score"] for r in results), 4),
        "pass_rate": round(sum(1 for r in results if r["passed"]) / len(results), 4),
        "mean_latency_ms": round(statistics.fmean(latencies), 1),
        "p95_latency_ms": round(percentile(latencies, 95), 1),
        "total_tokens": sum(r["tokens"] for r in results),
        "metrics": metric_means,
        "statuses": statuses,
    }


def evaluate_case(agent: RagAgent, case: dict) -> dict:
    """Run one case and return a plain dict that can be stored as an EvalResult."""
    result = agent.run(case["question"])
    scored = score_case(case, result)
    return {
        "case_id": case["id"],
        "question": case["question"],
        "answer": result.answer,
        "status": result.status,
        "metrics": scored.metrics,
        "score": scored.score,
        "passed": scored.passed,
        "latency_ms": round(result.latency_ms, 1),
        "tokens": result.prompt_tokens + result.completion_tokens,
        "tool_calls": result.tool_calls,
        "error": result.error,
    }


def execute_eval_run(
    db: Database,
    corpus: Corpus,
    settings: Settings,
    run_id: int,
    on_case: Callable[[int, int], None] | None = None,
) -> dict:
    """Execute a queued EvalRun. Progress is committed after every case."""
    with db.session() as session:
        run = session.get(EvalRun, run_id)
        dataset = session.get(EvalDataset, run.dataset_id)
        version = session.get(AgentVersion, run.agent_version_id)
        config = AgentConfig(**version.config)
        cases = list(dataset.cases)
        run.status = "running"
        run.progress_total = len(cases)
        run.progress_done = 0

    agent = RagAgent(config, ToolBox(corpus, db), settings)
    collected: list[dict] = []
    try:
        for index, case in enumerate(cases, start=1):
            outcome = evaluate_case(agent, case)
            collected.append(outcome)
            with db.session() as session:
                session.add(EvalResult(eval_run_id=run_id, **outcome))
                session.get(EvalRun, run_id).progress_done = index
            if on_case:
                on_case(index, len(cases))
        summary = summarize(collected)
        with db.session() as session:
            run = session.get(EvalRun, run_id)
            run.status = "completed"
            run.summary = summary
            run.finished_at = datetime.now(UTC)
        return summary
    except Exception as exc:  # noqa: BLE001 - the run must be marked as failed, whatever happened
        with db.session() as session:
            run = session.get(EvalRun, run_id)
            run.status = "failed"
            run.error = f"{type(exc).__name__}: {exc}"
            run.finished_at = datetime.now(UTC)
        raise
