"""FastAPI dependencies that read the shared objects from the application state."""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request

from ..config import Settings
from ..db import Database
from ..rag.corpus import Corpus

logger = logging.getLogger("agentlab")


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_corpus(request: Request) -> Corpus:
    return request.app.state.corpus


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def swallow_errors(func: Callable, *args) -> None:
    """Background jobs mark their own failures in the database, so only log them here."""
    try:
        func(*args)
    except Exception:  # noqa: BLE001
        logger.exception("background job failed")
