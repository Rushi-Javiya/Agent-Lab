"""Request bodies of the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..agents.rag_agent import AgentConfig
from ..providers import PROVIDER_NAMES


def _check_provider(name: str) -> str:
    if name not in PROVIDER_NAMES:
        raise ValueError(f"unknown provider '{name}', use one of {', '.join(PROVIDER_NAMES)}")
    return name


class ConfigBody(AgentConfig):
    @field_validator("provider")
    @classmethod
    def provider_must_exist(cls, value: str) -> str:
        return _check_provider(value)


class AgentCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]{1,58}[a-z0-9]$")
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    config: ConfigBody = Field(default_factory=ConfigBody)
    note: str = ""


class VersionCreate(BaseModel):
    config: ConfigBody
    note: str = ""


class RunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    version: int | None = None


class EvalRunCreate(BaseModel):
    dataset: str
    agent: str
    version: int | None = None


class BenchTarget(BaseModel):
    provider: str
    model: str = Field(min_length=1, max_length=120)

    @field_validator("provider")
    @classmethod
    def provider_must_exist(cls, value: str) -> str:
        return _check_provider(value)


class BenchmarkCreate(BaseModel):
    targets: list[BenchTarget] = Field(min_length=1, max_length=6)
    prompt_set: str = "qa-short"
    repeats: int = Field(1, ge=1, le=5)


class ExtractRequest(BaseModel):
    method: Literal["rules", "llm"] = "rules"
    provider: str = "mock"
    model: str = "mock-extractive"
    apply: bool = False

    @field_validator("provider")
    @classmethod
    def provider_must_exist(cls, value: str) -> str:
        return _check_provider(value)
