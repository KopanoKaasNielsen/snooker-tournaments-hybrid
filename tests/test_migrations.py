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
HEAD = "h20261120ops"


def configuration(tmp_path):
    return migration_config(f"sqlite:///{tmp_path / 'migration.db'}")


def test_revision_graph_has_one_complete_head(tmp_path):
    script = ScriptDirectory.from_config(configuration(tmp_path))
    assert script.get_heads() == [HEAD]
    assert [revision.revision for revision in script.walk_revisions()] == [
        HEAD,
        "g20261120fin",
        "f20261120auth",
        "e20261119db01",
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
            command.downgrade(config, "d27f9a18494f")
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
        "revision = 'test_failure'\ndown_revision = 'h20261120ops'\n"
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


def test_auth_upgrade_preserves_existing_players_and_downgrade_preserves_legacy(
    tmp_path,
):
    config = configuration(tmp_path)
    command.upgrade(config, "e20261119db01")
    migrated = make_engine(config.attributes["database_url"])
    try:
        from app.models import Player

        with sessionmaker(bind=migrated)() as session:
            session.add(Player(name="Pre-auth owner", balance=123.45))
            session.commit()
        command.upgrade(config, "head")
        command.check(config)
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT balance FROM players")) == 123.45
            assert connection.scalar(text("SELECT count(*) FROM users")) == 0
        command.downgrade(config, "e20261119db01")
        with migrated.connect() as connection:
            assert connection.scalar(text("SELECT balance FROM players")) == 123.45
            assert "users" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        command.check(config)
    finally:
        migrated.dispose()


def test_auth_downgrade_refuses_populated_authentication_tables(tmp_path):
    config = configuration(tmp_path)
    command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        from app.models import User
        from app.security import hash_password

        with sessionmaker(bind=migrated)() as session:
            session.add(
                User(
                    username="keep_account",
                    password_hash=hash_password("Keep this account password!"),
                )
            )
            session.commit()
        with pytest.raises(RuntimeError, match="authentication"):
            command.downgrade(config, "e20261119db01")
        with migrated.connect() as connection:
            assert (
                connection.scalar(text("SELECT username FROM users")) == "keep_account"
            )
            assert MigrationContext.configure(connection).get_current_revision() == HEAD
    finally:
        migrated.dispose()


def test_financial_additive_migration_preserves_all_existing_data(tmp_path):
    import sqlite3
    from contextlib import closing
    from scripts.verify_migrations import snapshot
    from app.models import (
        Player,
        Tournament,
        TournamentRegistration,
        WalletTransaction,
        User,
    )

    config = configuration(tmp_path)
    command.upgrade(config, "f20261120auth")
    migrated = make_engine(config.attributes["database_url"])
    try:
        with sessionmaker(bind=migrated)() as db:
            player = Player(name="Unknown currency preserved", balance=123.456789)
            tournament = Tournament(name="Historical price", entry_fee=17)
            db.add_all([player, tournament])
            db.flush()
            db.add_all(
                [
                    WalletTransaction(
                        player_id=player.id, type="deposit", amount=123.456789
                    ),
                    TournamentRegistration(
                        player_id=player.id,
                        tournament_id=tournament.id,
                        contribution=11,
                        paid=True,
                    ),
                    User(
                        username="existing_account",
                        password_hash="preserved-test-hash",
                        player_id=player.id,
                    ),
                ]
            )
            db.commit()
        target = tmp_path / "migration.db"
        with closing(sqlite3.connect(target)) as db:
            before = snapshot(db)
        command.upgrade(config, "head")
        command.check(config)
        with closing(sqlite3.connect(target)) as db:
            after = snapshot(db)
        assert all(after[name] == rows for name, rows in before.items())
        assert after["financial_wallets"] == after["financial_ledger_entries"] == []
        command.downgrade(config, "f20261120auth")
        with closing(sqlite3.connect(target)) as db:
            assert snapshot(db) == before
        command.upgrade(config, "head")
        command.check(config)
    finally:
        migrated.dispose()


def test_financial_populated_downgrade_is_refused(tmp_path):
    from app.models import Player
    from app.services.financial_wallets import FinancialWalletService

    config = configuration(tmp_path)
    command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        with sessionmaker(bind=migrated)() as db:
            player = Player(name="Do not drop exact account")
            db.add(player)
            db.commit()
            pid = player.id
        account = FinancialWalletService(migrated).open_wallet(pid, currency="BWP")
        with pytest.raises(RuntimeError, match="Populated financial data"):
            command.downgrade(config, "f20261120auth")
        with migrated.connect() as db:
            assert db.scalar(text("SELECT id FROM financial_wallets")) == account.id
            assert MigrationContext.configure(db).get_current_revision() == HEAD
    finally:
        migrated.dispose()


def test_migrated_financial_ledger_triggers_match_metadata_and_are_effective(tmp_path):
    from decimal import Decimal
    from uuid import uuid4
    from sqlalchemy.exc import IntegrityError
    from app.financial_schema import TRIGGERS
    from app.models import Player
    from app.services.financial_wallets import FinancialWalletService

    config = configuration(tmp_path)
    command.upgrade(config, "head")
    migrated = make_engine(config.attributes["database_url"])
    try:
        with sessionmaker(bind=migrated)() as db:
            player = Player(name="Migrated trigger check")
            db.add(player)
            db.commit()
            pid = player.id
        service = FinancialWalletService(migrated)
        account = service.open_wallet(pid, currency="BWP")
        service.post(
            account.id,
            kind="deposit",
            amount=Decimal("0.30"),
            currency="BWP",
            idempotency_key=str(uuid4()),
        )
        with migrated.connect() as db:
            actual = dict(
                db.execute(
                    text(
                        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='financial_ledger_entries'"
                    )
                ).all()
            )
            assert set(actual) == set(TRIGGERS)
            assert all(
                " ".join(actual[name].split()) == " ".join(sql.split())
                for name, sql in TRIGGERS.items()
            )
            with pytest.raises(IntegrityError, match="append-only"):
                db.execute(text("DELETE FROM financial_ledger_entries"))
            db.rollback()
        assert service.reconcile()[0].consistent
    finally:
        migrated.dispose()


def test_operation_migration_preserves_existing_wallets_ledger_and_auth(tmp_path):
    import sqlite3
    from contextlib import closing
    from decimal import Decimal
    from uuid import uuid4
    from app.models import Player, User
    from app.operation_schema import OPERATION_TRIGGERS, operation_triggers_match
    from app.services.financial_wallets import FinancialWalletService
    from scripts.verify_migrations import snapshot, verify_existing_copy

    config = configuration(tmp_path)
    command.upgrade(config, "g20261120fin")
    engine = make_engine(config.attributes["database_url"])
    try:
        with sessionmaker(bind=engine)() as db:
            player = Player(name="Preserve existing exact funds")
            db.add(player)
            db.flush()
            db.add(
                User(
                    username="preserved_owner",
                    password_hash="test-only-no-login",
                    player_id=player.id,
                )
            )
            db.commit()
            pid = player.id
        wallet_service = FinancialWalletService(engine)
        wallet = wallet_service.open_wallet(pid, currency="BWP")
        wallet_service.post(
            wallet.id,
            kind="deposit",
            amount=Decimal("10.00"),
            currency="BWP",
            idempotency_key=str(uuid4()),
        )
        source = tmp_path / "migration.db"
        with closing(sqlite3.connect(source)) as db:
            before = snapshot(db)
        # Compatibility tool must support a versioned, populated Task 04A source.
        verify_existing_copy(source, tmp_path / "versioned-compatible-copy.db")
        command.upgrade(config, "head")
        command.check(config)
        with closing(sqlite3.connect(source)) as db:
            after = snapshot(db)
        assert all(after[name] == rows for name, rows in before.items())
        assert after["financial_operations"] == after["financial_operation_audit"] == []
        with engine.connect() as db:
            assert operation_triggers_match(db)
            actual = dict(
                db.execute(
                    text("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
                ).all()
            )
            assert all(
                " ".join(actual[name].split()) == " ".join(sql.split())
                for name, sql in OPERATION_TRIGGERS.items()
            )
        command.downgrade(config, "g20261120fin")
        with closing(sqlite3.connect(source)) as db:
            assert snapshot(db) == before
        command.upgrade(config, "head")
        assert wallet_service.reconcile()[0].balance == Decimal("10.00")
    finally:
        engine.dispose()


def test_populated_operations_downgrade_is_refused(tmp_path):
    from decimal import Decimal
    from uuid import uuid4
    from app.models import Player, User, FinancialOperation
    from app.security import create_session
    from app.services.financial_wallets import FinancialWalletService
    from app.services.financial_operations import FinancialOperationService

    config = configuration(tmp_path)
    command.upgrade(config, "head")
    engine = make_engine(config.attributes["database_url"])
    try:
        with sessionmaker(bind=engine)() as db:
            player = Player(name="Operation history must stay")
            db.add(player)
            db.flush()
            user = User(
                username="operation_owner",
                password_hash="test-only-not-used",
                player_id=player.id,
            )
            db.add(user)
            db.flush()
            token, _ = create_session(db, user)
            db.commit()
            pid = player.id
        wallet = FinancialWalletService(engine).open_wallet(pid, currency="BWP")
        operation = FinancialOperationService(engine).request(
            token,
            wallet.id,
            kind="deposit",
            amount=Decimal("1"),
            currency="BWP",
            idempotency_key=str(uuid4()),
        )
        with pytest.raises(RuntimeError, match="Populated financial operations"):
            command.downgrade(config, "g20261120fin")
        with sessionmaker(bind=engine)() as db:
            assert db.get(FinancialOperation, operation.id).status == "PENDING"
        with engine.connect() as db:
            assert MigrationContext.configure(db).get_current_revision() == HEAD
    finally:
        engine.dispose()
