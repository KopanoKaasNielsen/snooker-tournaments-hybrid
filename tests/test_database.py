"""Database lifecycle tests; every connection targets a disposable SQLite file."""

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import database
from app.database import make_engine
from app.db_cli import require_development_database
from app.init_db import DEFAULT_PLAYERS, DEFAULT_TOURNAMENTS, seed_data
from app.models import Player, Tournament, TournamentRegistration
from app.time import utc_now
from tests.conftest import TEST_SQLITE_URL, TestingSessionLocal, engine

ROOT = Path(__file__).resolve().parents[1]


def test_database_url_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert database.get_database_url() == "sqlite:///./snooker.db"
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/explicit-test.db")
    assert database.get_database_url() == "sqlite:////tmp/explicit-test.db"


def test_test_databases_are_isolated():
    assert "snooker-tests-" in TEST_SQLITE_URL
    assert TEST_SQLITE_URL != database.get_database_url()
    assert Path(database.engine.url.database).resolve() != ROOT / "snooker.db"
    with TestingSessionLocal() as session:
        assert session.query(Player).count() == 0


@pytest.mark.parametrize("already_exists", [False, True])
def test_imports_do_not_create_or_mutate_databases(tmp_path, already_exists):
    target = tmp_path / "import.db"
    if already_exists:
        import sqlite3

        with sqlite3.connect(target) as connection:
            connection.execute("CREATE TABLE sentinel (value TEXT)")
            connection.execute("INSERT INTO sentinel VALUES ('preserve')")
        before = target.read_bytes()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{target}"}
    subprocess.run(
        [
            sys.executable,
            "-W",
            "error",
            "-c",
            "import os\n"
            "import app.database, app.models, app.main, app.init_db, app.db_cli\n"
            "assert str(app.database.engine.url) == os.environ['DATABASE_URL']\n"
            "from fastapi.testclient import TestClient\n"
            "with TestClient(app.main.app) as client:\n"
            "    assert client.get('/health').json() == {'ok': True}\n",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    if already_exists:
        assert target.read_bytes() == before
    else:
        assert not target.exists()


def test_failed_request_rolls_back_and_closes_session(monkeypatch):
    session = TestingSessionLocal()
    rollback = Mock(wraps=session.rollback)
    close = Mock(wraps=session.close)
    monkeypatch.setattr(session, "rollback", rollback)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()
    db = next(dependency)
    db.add(Player(name="must roll back"))
    db.flush()
    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))
    rollback.assert_called_once()
    close.assert_called_once()
    with TestingSessionLocal() as check:
        assert check.query(Player).count() == 0


def test_successful_request_closes_without_implicit_commit(monkeypatch):
    session = TestingSessionLocal()
    close = Mock(wraps=session.close)
    monkeypatch.setattr(session, "close", close)
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    dependency = database.get_db()
    db = next(dependency)
    db.add(Player(name="uncommitted"))
    db.flush()
    with pytest.raises(StopIteration):
        next(dependency)
    close.assert_called_once()
    with TestingSessionLocal() as check:
        assert check.query(Player).count() == 0


def test_foreign_keys_enforced_on_multiple_connections():
    with engine.connect() as first, engine.connect() as second:
        assert first.scalar(text("PRAGMA foreign_keys")) == 1
        assert second.scalar(text("PRAGMA foreign_keys")) == 1
    with TestingSessionLocal() as session:
        session.add(TournamentRegistration(tournament_id=999, player_id=999))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(TournamentRegistration).count() == 0


def test_duplicate_registration_constraint_and_recovery():
    with TestingSessionLocal() as session:
        player, tournament = Player(name="One"), Tournament(name="Cup")
        session.add_all([player, tournament])
        session.flush()
        session.add(
            TournamentRegistration(tournament_id=tournament.id, player_id=player.id)
        )
        session.commit()
        session.add(
            TournamentRegistration(tournament_id=tournament.id, player_id=player.id)
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert session.query(TournamentRegistration).count() == 1


def test_repeatable_explicit_seed_preserves_existing_values():
    with TestingSessionLocal() as session:
        session.add(Player(name=DEFAULT_PLAYERS[0], balance=12.5, rating=1777))
        session.commit()
    seed_data(TestingSessionLocal)
    seed_data(TestingSessionLocal)
    with TestingSessionLocal() as session:
        assert session.query(Player).count() == len(DEFAULT_PLAYERS)
        assert session.query(Tournament).count() == len(DEFAULT_TOURNAMENTS)
        existing = session.query(Player).filter_by(name=DEFAULT_PLAYERS[0]).one()
        assert (existing.balance, existing.rating) == (12.5, 1777)


def test_seed_failure_rolls_back_all_inserts():
    session = TestingSessionLocal()
    rollback = Mock(wraps=session.rollback)
    close = Mock(wraps=session.close)
    session.rollback, session.close = rollback, close

    def failing_commit():
        session.flush()
        raise RuntimeError("commit failed")

    session.commit = failing_commit
    with pytest.raises(RuntimeError, match="commit failed"):
        seed_data(lambda: session)
    rollback.assert_called_once()
    close.assert_called_once()
    with TestingSessionLocal() as check:
        assert check.query(Player).count() == 0
        assert check.query(Tournament).count() == 0


@pytest.mark.parametrize("environment", [None, "production", "staging"])
def test_demo_setup_refuses_non_development(monkeypatch, environment):
    if environment is None:
        monkeypatch.delenv("APP_ENV", raising=False)
    else:
        monkeypatch.setenv("APP_ENV", environment)
    with pytest.raises(ValueError, match="APP_ENV=development"):
        require_development_database()


def test_demo_setup_refuses_original_database(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{ROOT / 'snooker.db'}")
    with pytest.raises(ValueError, match="refuses"):
        require_development_database()


def test_engine_creation_is_lazy(tmp_path):
    target = tmp_path / "lazy.db"
    test_engine = make_engine(f"sqlite:///{target}")
    test_engine.dispose()
    assert not target.exists()


def test_utc_default_preserves_naive_storage_contract():
    from datetime import datetime, timezone

    before = datetime.now(timezone.utc).replace(tzinfo=None)
    value = utc_now()
    assert value.tzinfo is None
    assert before <= value <= datetime.now(timezone.utc).replace(tzinfo=None)
