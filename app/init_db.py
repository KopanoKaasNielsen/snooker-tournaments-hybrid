"""Utilities for seeding the SQLite database with default data."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterable, Iterator

from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal

# Default records used throughout the tests and during local development. The
# lists are intentionally small to keep the seed procedure quick and fully
# idempotent.
DEFAULT_PLAYERS: tuple[str, ...] = (
    "Ronnie O'Sullivan",
    "Mark Selby",
    "Judd Trump",
    "Neil Robertson",
    "John Higgins",
    "Ding Junhui",
    "Shaun Murphy",
    "Kyren Wilson",
)
DEFAULT_TOURNAMENTS: tuple[str, ...] = ("Botswana Open",)


@contextmanager
def _session_scope(factory: Callable[[], Session] = SessionLocal) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def _ensure_records(session: Session, model, names: Iterable[str]) -> bool:
    """Insert any records from ``names`` that do not yet exist."""

    created = False
    for name in names:
        if not session.query(model).filter_by(name=name).first():
            session.add(model(name=name))
            created = True
    return created


def seed_data(session_factory: Callable[[], Session] = SessionLocal) -> None:
    """Seed the database with default players and tournaments.

    The function is safe to call multiple times; it will only insert missing
    records and therefore keeps the database free from duplicates.
    """

    with _session_scope(session_factory) as session:
        created_players = _ensure_records(session, models.Player, DEFAULT_PLAYERS)
        created_tournaments = _ensure_records(session, models.Tournament, DEFAULT_TOURNAMENTS)

        # ``session.commit`` is handled by ``_session_scope``; however, issuing an
        # explicit flush makes it easier to reason about when the objects hit the
        # database during debugging and keeps the function transparent.
        if created_players or created_tournaments:
            session.flush()


if __name__ == "__main__":
    seed_data()
