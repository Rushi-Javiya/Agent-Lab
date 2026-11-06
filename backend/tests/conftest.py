from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.records import load_reference_records
from app.agents.tools import ToolBox
from app.db import Database
from app.providers import ProviderError
from app.rag.corpus import Corpus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    return Corpus.load(DATA_DIR / "docs")


@pytest.fixture()
def db() -> Database:
    database = Database("sqlite://")
    database.create_all()
    load_reference_records(database, DATA_DIR)
    return database


@pytest.fixture()
def toolbox(corpus: Corpus, db: Database) -> ToolBox:
    return ToolBox(corpus, db)


class FailingProvider:
    """A provider whose server is down. Fails instantly instead of waiting for a timeout."""

    name = "failing"

    def chat(self, *args, **kwargs):
        raise ProviderError("server unreachable")

    def list_models(self) -> list[str]:
        return []

    def is_available(self) -> bool:
        return False


@pytest.fixture()
def unreachable(monkeypatch):
    for target in (
        "app.agents.rag_agent.get_provider",
        "app.agents.extraction.get_provider",
        "app.bench.runner.get_provider",
    ):
        monkeypatch.setattr(target, lambda name, settings, transport=None: FailingProvider())
