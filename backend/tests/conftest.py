from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.records import load_reference_records
from app.agents.tools import ToolBox
from app.db import Database
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
