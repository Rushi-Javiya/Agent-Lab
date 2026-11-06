"""Model benchmarks."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select

from ..bench.runner import execute_benchmark_run, list_prompt_sets, load_prompt_set
from ..config import Settings
from ..db import Database
from ..models import BenchmarkResult, BenchmarkRun
from ..rag.corpus import Corpus
from .deps import get_corpus, get_db, get_settings, swallow_errors
from .schemas import BenchmarkCreate
from .serializers import benchmark_out

router = APIRouter(prefix="/api", tags=["benchmarks"])


@router.get("/benchmarks/prompt-sets")
def prompt_sets(settings: Settings = Depends(get_settings)) -> list[dict]:
    return list_prompt_sets(settings.data_dir)


@router.post("/benchmarks/runs", status_code=202)
def start_benchmark(
    body: BenchmarkCreate,
    background: BackgroundTasks,
    db: Database = Depends(get_db),
    corpus: Corpus = Depends(get_corpus),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        load_prompt_set(settings.data_dir, body.prompt_set)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    with db.session() as session:
        run = BenchmarkRun(prompt_set=body.prompt_set, repeats=body.repeats, status="queued")
        run.results = [BenchmarkResult(provider=t.provider, model=t.model) for t in body.targets]
        session.add(run)
        session.flush()
        run_id = run.id
        out = benchmark_out(run)

    background.add_task(swallow_errors, execute_benchmark_run, db, corpus, settings, run_id)
    return out


@router.get("/benchmarks/runs")
def list_benchmarks(limit: int = 20, db: Database = Depends(get_db)) -> list[dict]:
    with db.session() as session:
        stmt = select(BenchmarkRun).order_by(BenchmarkRun.id.desc()).limit(max(1, min(limit, 100)))
        return [benchmark_out(run) for run in session.scalars(stmt).all()]


@router.get("/benchmarks/runs/{run_id}")
def get_benchmark(run_id: int, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        run = session.get(BenchmarkRun, run_id)
        if run is None:
            raise HTTPException(404, "Benchmark run not found")
        return benchmark_out(run)
