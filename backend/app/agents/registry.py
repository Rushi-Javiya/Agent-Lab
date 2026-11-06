"""Creating and reading agents and their immutable versions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Agent, AgentRun, AgentVersion
from .rag_agent import AgentConfig, AgentResult


def create_agent(
    session: Session,
    slug: str,
    name: str,
    description: str,
    config: AgentConfig,
    note: str = "",
) -> Agent:
    agent = Agent(slug=slug, name=name, description=description)
    agent.versions.append(AgentVersion(version=1, config=config.model_dump(), note=note))
    session.add(agent)
    session.flush()
    return agent


def add_version(
    session: Session, agent: Agent, config: AgentConfig, note: str = ""
) -> AgentVersion:
    next_number = (agent.versions[-1].version if agent.versions else 0) + 1
    version = AgentVersion(
        agent_id=agent.id, version=next_number, config=config.model_dump(), note=note
    )
    session.add(version)
    session.flush()
    session.refresh(agent)
    return version


def get_agent(session: Session, ref: str | int) -> Agent | None:
    if isinstance(ref, int) or str(ref).isdigit():
        return session.get(Agent, int(ref))
    return session.scalar(select(Agent).where(Agent.slug == ref))


def get_version(agent: Agent, number: int | None = None) -> AgentVersion | None:
    if not agent.versions:
        return None
    if number is None:
        return agent.versions[-1]
    return next((v for v in agent.versions if v.version == number), None)


def record_run(session: Session, version: AgentVersion, result: AgentResult) -> AgentRun:
    run = AgentRun(
        agent_version_id=version.id,
        question=result.question,
        answer=result.answer,
        raw_answer=result.raw_answer,
        status=result.status,
        citations=result.citations,
        tool_calls=result.tool_calls,
        validation_errors=result.validation_errors,
        latency_ms=result.latency_ms,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        llm_calls=result.llm_calls,
        error=result.error,
    )
    session.add(run)
    session.flush()
    return run
