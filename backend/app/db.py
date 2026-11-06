"""Database setup. SQLite by default, any SQLAlchemy URL works through AGENTLAB_DATABASE_URL."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    """Owns the engine and the session factory so tests can create isolated instances."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.engine = self._make_engine(url)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _make_engine(url: str) -> Engine:
        if not url.startswith("sqlite"):
            return create_engine(url, future=True)

        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url.endswith("sqlite://"):
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, future=True, **kwargs)

        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_connection, _record) -> None:  # pragma: no cover - trivial
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine

    def create_all(self) -> None:
        from . import models  # noqa: F401  (registers the tables)

        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
