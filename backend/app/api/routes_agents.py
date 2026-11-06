"""Health, agents, versions and ad-hoc runs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..agents.rag_agent import AgentConfig, RagAgent
from ..agents.registry import add_version, create_agent, get_agent, get_version, record_run
from ..agents.tools import ToolBox
from ..config import Settings
from ..db import Database
from ..models import Agent, AgentRun, AgentVersion
from ..providers import provider_status
from ..rag.corpus import Corpus
from .deps import get_corpus, get_db, get_settings
from .schemas import AgentCreate, RunRequest, VersionCreate
from .serializers import agent_detail, agent_summary, run_out, version_out

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "providers": provider_status(settings)}


@router.get("/agents")
def list_agents(db: Database = Depends(get_db)) -> list[dict]:
    with db.session() as session:
        agents = session.scalars(select(Agent).order_by(Agent.id)).all()
        return [agent_summary(session, agent) for agent in agents]


@router.post("/agents", status_code=201)
def create(body: AgentCreate, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        if get_agent(session, body.slug) is not None:
            raise HTTPException(409, f"An agent with slug '{body.slug}' already exists")
        agent = create_agent(
            session,
            body.slug,
            body.name,
            body.description,
            AgentConfig(**body.config.model_dump()),
            body.note,
        )
        return agent_detail(session, agent)


@router.get("/agents/{ref}")
def get_one(ref: str, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        agent = get_agent(session, ref)
        if agent is None:
            raise HTTPException(404, "Agent not found")
        return agent_detail(session, agent)


@router.post("/agents/{ref}/versions", status_code=201)
def new_version(ref: str, body: VersionCreate, db: Database = Depends(get_db)) -> dict:
    with db.session() as session:
        agent = get_agent(session, ref)
        if agent is None:
            raise HTTPException(404, "Agent not found")
        version = add_version(session, agent, AgentConfig(**body.config.model_dump()), body.note)
        return version_out(session, version)


@router.post("/agents/{ref}/run")
def run_agent(
    ref: str,
    body: RunRequest,
    db: Database = Depends(get_db),
    corpus: Corpus = Depends(get_corpus),
    settings: Settings = Depends(get_settings),
) -> dict:
    with db.session() as session:
        agent = get_agent(session, ref)
        if agent is None:
            raise HTTPException(404, "Agent not found")
        version = get_version(agent, body.version)
        if version is None:
            raise HTTPException(404, "Version not found")
        config = AgentConfig(**version.config)
        version_id, version_number = version.id, version.version

    # The model call happens outside of the database session, it can take a while.
    result = RagAgent(config, ToolBox(corpus, db), settings).run(body.question)

    with db.session() as session:
        version = session.get(AgentVersion, version_id)
        run = record_run(session, version, result)
        return run_out(run, version_number)


@router.get("/agents/{ref}/runs")
def list_runs(ref: str, limit: int = 20, db: Database = Depends(get_db)) -> list[dict]:
    with db.session() as session:
        agent = get_agent(session, ref)
        if agent is None:
            raise HTTPException(404, "Agent not found")
        numbers = {v.id: v.version for v in agent.versions}
        runs = session.scalars(
            select(AgentRun)
            .where(AgentRun.agent_version_id.in_(numbers))
            .order_by(AgentRun.id.desc())
            .limit(max(1, min(limit, 100)))
        ).all()
        return [run_out(r, numbers[r.agent_version_id]) for r in runs]
