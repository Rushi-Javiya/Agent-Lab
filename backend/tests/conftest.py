from __future__ import annotations

from pathlib import Path

import pytest

from app.rag.corpus import Corpus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def corpus() -> Corpus:
    return Corpus.load(DATA_DIR / "docs")
