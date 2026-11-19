"""Shared database configuration. Importing this module performs no database I/O."""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
Base = declarative_base(metadata=MetaData(naming_convention=naming_convention))


def get_database_url() -> str:
    """Environment wins; .env files are not implicitly loaded or logged."""
    return os.environ.get("DATABASE_URL", "sqlite:///./snooker.db")


def make_engine(url: str, *, foreign_keys: bool = True) -> Engine:
    """Create a lazy engine; SQLite FK checks apply to every application connection."""
    sqlite = url.startswith("sqlite")
    result = create_engine(
        url, connect_args={"check_same_thread": False} if sqlite else {}
    )
    if sqlite and foreign_keys:

        @event.listens_for(result, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return result


SQLALCHEMY_DATABASE_URL = get_database_url()
engine = make_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """Services own commits; roll back failed requests and always close sessions."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
