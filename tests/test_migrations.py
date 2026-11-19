"""Real Alembic operations, always against pytest temporary databases."""

import os
from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, make_engine
from app.db_cli import migration_config
from app.init_db import DEFAULT_PLAYERS

ROOT = Path(__file__).resolve().parents[1]
HEAD = "e20261119db01"


def configuration(tmp_path):
    return migration_config(f"sqlite:///{tmp_path / 'migration.db'}")


def test_revision_graph_has_one_complete_head(tmp_path):
    script = ScriptDirectory.from_config(configuration(tmp_path))
    assert script.get_heads() == [HEAD]
    assert [revision.revision for revision in script.walk_revisions()] == [
        HEAD,
        "d27f9a18494f",
        "dd093dfa2ebf",
    ]


def test_fresh_migrations_match_models_and_roundtrip_empty_schema(tmp_path):
    config = configuration(tmp_path)
    command.history(config)
    command.heads(config)
    command.current(config)
    command.upgrade(config, "head")
    command.current(config)
    command.check(config)
    migrated = make_engine(config.attributes["database_url"])
    try:
        with migrated.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == HEAD
            assert (
                compare_metadata(MigrationContext.configure(connection), Base.metadata)
                == []
            )
            assert connection.scalar(text("SELECT count(*) FROM players")) == 0
            assert (
                connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
            )
        command.downgrade(config, "base")
        assert set(inspect(migrated).get_table_names()) == {"alembic_version"}
        command.upgrade(config, "head")
        command.check(config)
    finally:
        migrated.dispose()


def test_populated_historical_schema_is_refused_without_inferred_finances(tmp_path):
    config = configuration(tmp_path)
    command.upgrade(config, "d27f9a18494f")
    migrated = make_engine(config.attributes["database_url"])
    try:
        with migrated.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO players (id, name, rating) VALUES (1, 'Legacy', 1500)"
                )
            )
        with pytest.raises(RuntimeError, match="reviewed data migration"):
            command.upgrade(config, "head")
        with migrated.connect() as connection:
            assert (
                MigrationContext.configure(connection).get_current_revision()
                == "d27f9a18494f"
            )
            assert (
                connection.scalar(text("SELECT rating FROM players WHERE id=1")) == 1500
            )
            assert "wallet_transactions" not in inspect(connection).get_table_names()
    finally:
        migrated.dispose()


def test_populated_head_downgrade_is_refused(tmp_path):
    config = configuration(tmp_path)
    command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        from app.models import Player

        with sessionmaker(bind=migrated)() as session:
            session.add(Player(name="Keep", balance=42.25))
            session.commit()
        with pytest.raises(RuntimeError, match="reviewed data migration"):
            command.downgrade(config, "-1")
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT balance FROM players")) == 42.25
            assert MigrationContext.configure(connection).get_current_revision() == HEAD
    finally:
        migrated.dispose()


def test_adoption_rolls_back_when_foreign_keys_invalid(tmp_path):
    config = configuration(tmp_path)
    command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        # Foreign keys are disabled only on Alembic's private connection. Inject an
        # orphan using a separate engine to verify final validation rolls back adoption.
        unsafe = make_engine(config.attributes["database_url"], foreign_keys=False)
        with unsafe.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO wallet_transactions VALUES (1, 999, 'deposit', 1.0, '2026-01-01')"
                )
            )
        unsafe.dispose()
        with pytest.raises(RuntimeError, match="Foreign key violations"):
            command.stamp(config, "base")
        with migrated.connect() as connection:
            assert MigrationContext.configure(connection).get_current_revision() == HEAD
    finally:
        migrated.dispose()


def test_explicit_development_cli_and_repeatable_demo(tmp_path):
    target = tmp_path / "cli.db"
    env = {
        **os.environ,
        "APP_ENV": "development",
        "DATABASE_URL": f"sqlite:///{target}",
    }

    def run(*args):
        return subprocess.run(
            [sys.executable, "-m", "app.db_cli", *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    result = run("seed-demo")
    assert result.returncode == 2 and "--confirm-demo" in result.stderr
    assert not target.exists()
    result = run("init")
    assert result.returncode == 0, result.stderr
    migrated = make_engine(env["DATABASE_URL"])
    try:
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM players")) == 0
        for _ in range(2):
            result = run("seed-demo", "--confirm-demo")
            assert result.returncode == 0, result.stderr
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM players")) == len(
                DEFAULT_PLAYERS
            )
    finally:
        migrated.dispose()


def test_failed_migration_rolls_back_ddl_and_revision(tmp_path):
    import shutil

    copy = tmp_path / "migrations"
    shutil.copytree(ROOT / "migrations", copy)
    config = configuration(tmp_path)
    config.set_main_option("script_location", str(copy))
    command.upgrade(config, "head")
    (copy / "versions" / "test_failure.py").write_text(
        "from alembic import op\nimport sqlalchemy as sa\n"
        "revision = 'test_failure'\ndown_revision = 'e20261119db01'\n"
        "def upgrade():\n"
        "    op.create_table('must_rollback', sa.Column('id', sa.Integer()))\n"
        "    raise RuntimeError('deliberate failure')\n"
        "def downgrade():\n    pass\n"
    )
    with pytest.raises(RuntimeError, match="deliberate failure"):
        command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        with migrated.connect() as connection:
            assert "must_rollback" not in inspect(connection).get_table_names()
            assert MigrationContext.configure(connection).get_current_revision() == HEAD
    finally:
        migrated.dispose()


def test_unversioned_schema_copy_adoption_preserves_source_and_rows(tmp_path):
    from app.init_db import seed_data
    from scripts.verify_migrations import verify_existing_copy

    source = tmp_path / "unversioned.db"
    unversioned = make_engine(f"sqlite:///{source}")
    try:
        Base.metadata.create_all(unversioned)
        seed_data(sessionmaker(bind=unversioned))
    finally:
        unversioned.dispose()
    before = source.read_bytes()
    verify_existing_copy(source, tmp_path / "compatibility-copy.db")
    assert source.read_bytes() == before


def test_inconsistent_schema_copy_is_not_stamped(tmp_path):
    import sqlite3
    from scripts.verify_migrations import verify_existing_copy

    source = tmp_path / "inconsistent.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE players (id INTEGER PRIMARY KEY)")
    target = tmp_path / "inconsistent-copy.db"
    with pytest.raises(RuntimeError, match="schema differs"):
        verify_existing_copy(source, target)
    with sqlite3.connect(target) as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name='alembic_version'"
            ).fetchall()
            == []
        )
