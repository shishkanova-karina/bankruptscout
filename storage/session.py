"""Инициализация движка БД, фабрика сессий, контекстный менеджер транзакций."""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from storage.models import Base

_db_engine: Engine | None = None
_session_maker: sessionmaker[Session] | None = None


def resolve_db_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./data/scraper.db")


def create_engine_instance() -> Engine:
    global _db_engine
    if _db_engine is not None:
        return _db_engine

    url = resolve_db_url()
    extra = {}
    if url.startswith("sqlite"):
        extra["check_same_thread"] = False

    verbose = os.environ.get("SQLALCHEMY_ECHO", "").lower() == "true"
    _db_engine = create_engine(url, echo=verbose, connect_args=extra)
    return _db_engine


def build_session_maker() -> sessionmaker[Session]:
    global _session_maker
    if _session_maker is not None:
        return _session_maker

    _session_maker = sessionmaker(
        bind=create_engine_instance(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _session_maker


@contextmanager
def managed_session() -> Generator[Session, None, None]:
    factory = build_session_maker()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize_tables() -> None:
    """Создаёт все таблицы в БД по описанным моделям."""
    url = resolve_db_url()
    if url.startswith("sqlite"):
        Path("data").mkdir(parents=True, exist_ok=True)
    engine = create_engine_instance()
    Base.metadata.create_all(bind=engine)
