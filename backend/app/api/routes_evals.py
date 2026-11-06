"""Datasets, evaluation runs and comparisons."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select

from ..agents.registry import get_agent, get_version
from ..config import Settings
from ..db import Database
from ..evals.compare import compare_results
from ..evals.harness import execute_eval_run
from ..models import EvalDataset, EvalRun
from ..rag.corpus import Corpus
from .deps import get_corpus, get_db, get_settings, swallow_errors
from .schemas import EvalRunCreate
from .serializers import eval_run_out

router = APIRouter(prefix="/api", tags=["evals"])


def _dataset_out(dataset: EvalDataset, with_cases: bool = False) -> dict:
    out = {
        "id": dataset.id,
        "slug": dataset.slug,
        "name": dataset.name,
        "kind": dataset.kind,
        "description": dataset.description,
        "case_count": len(dataset.cases),
    }
    if with_cases:
        out["cases"] = dataset.cases
    return out


@router.get("/datasets")
def list_datasets(db: Database = Depends(get_db)) -> list[dict]:
    with db.session() as session:
        return [
            _dataset_out(d) for d in session.scalars(select(EvalDataset).order_by(EvalDataset.id))
        ]


@router.get("/datasets/{slug}")
def get_dataset(slug: str, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        dataset = session.scalar(select(EvalDataset).where(EvalDataset.slug == slug))
        if dataset is None:
            raise HTTPException(404, "Dataset not found")
        return _dataset_out(dataset, with_cases=True)


@router.post("/evals/runs", status_code=202)
def start_eval(
    body: EvalRunCreate,
    background: BackgroundTasks,
    db: Database = Depends(get_db),
    corpus: Corpus = Depends(get_corpus),
    settings: Settings = Depends(get_settings),
) -> dict:
    with db.session() as session:
        dataset = session.scalar(select(EvalDataset).where(EvalDataset.slug == body.dataset))
        if dataset is None:
            raise HTTPException(404, "Dataset not found")
        agent = get_agent(session, body.agent)
        if agent is None:
            raise HTTPException(404, "Agent not found")
        version = get_version(agent, body.version)
        if version is None:
            raise HTTPException(404, "Version not found")
        run = EvalRun(
            dataset_id=dataset.id,
            agent_version_id=version.id,
            status="queued",
            progress_total=len(dataset.cases),
        )
        session.add(run)
        session.flush()
        run_id = run.id
        out = eval_run_out(session, run)

    background.add_task(swallow_errors, execute_eval_run, db, corpus, settings, run_id)
    return out


@router.get("/evals/runs")
def list_eval_runs(
    agent: str | None = None, limit: int = 30, db: Database = Depends(get_db)
) -> list[dict]:
    with db.session() as session:
        stmt = select(EvalRun).order_by(EvalRun.id.desc()).limit(max(1, min(limit, 100)))
        if agent:
            found = get_agent(session, agent)
            if found is None:
                raise HTTPException(404, "Agent not found")
            stmt = stmt.where(EvalRun.agent_version_id.in_([v.id for v in found.versions]))
        return [eval_run_out(session, run) for run in session.scalars(stmt).all()]


@router.get("/evals/compare")
def compare(baseline: int, candidate: int, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        runs = {}
        for name, run_id in (("baseline", baseline), ("candidate", candidate)):
            run = session.get(EvalRun, run_id)
            if run is None:
                raise HTTPException(404, f"Eval run {run_id} not found")
            runs[name] = run
        a = eval_run_out(session, runs["baseline"], include_results=True)
        b = eval_run_out(session, runs["candidate"], include_results=True)
    if a["dataset"]["id"] != b["dataset"]["id"]:
        raise HTTPException(422, "Both runs must use the same dataset")
    comparison = compare_results(a["results"], b["results"])
    for item in (a, b):
        item.pop("results")
    return {"baseline": a, "candidate": b, **comparison}


@router.get("/evals/runs/{run_id}")
def get_eval_run(run_id: int, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            raise HTTPException(404, "Eval run not found")
        return eval_run_out(session, run, include_results=True)
