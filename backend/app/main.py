"""FastAPI application factory. Run with: uvicorn app.main:create_app --factory"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import routes_agents, routes_bench, routes_docs, routes_evals
from .config import Settings, get_settings
from .db import Database
from .rag.corpus import Corpus
from .seed import seed_all


def create_app(
    settings: Settings | None = None,
    db: Database | None = None,
    corpus: Corpus | None = None,
    seed: bool = True,
) -> FastAPI:
    settings = settings or get_settings()
    database = db or Database(settings.database_url)
    database.create_all()
    if seed:
        seed_all(database, settings.data_dir)

    app = FastAPI(
        title="Agent Lab",
        version=__version__,
        description="Agent registry, repeatable evaluations and local LLM benchmarks.",
    )
    app.state.settings = settings
    app.state.db = database
    app.state.corpus = corpus or Corpus.load(settings.data_dir / "docs")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (routes_agents, routes_evals, routes_bench, routes_docs):
        app.include_router(module.router)
    return app
