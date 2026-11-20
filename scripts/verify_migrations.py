"""Verify migrations only in temporary databases, optionally cloning a read-only source."""

from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import tempfile

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import OperationalError
from sqlalchemy import MetaData

from app.database import Base, make_engine
from app.financial_schema import ledger_triggers_match
from app.db_cli import migration_config
from app import models  # noqa: F401


def snapshot(connection):
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version' ORDER BY name"
        )
    ]
    result = {}
    for name in tables:
        quoted = '"' + name.replace('"', '""') + '"'
        columns = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
        order = ", ".join(str(index + 1) for index in range(len(columns)))
        result[name] = connection.execute(
            f"SELECT * FROM {quoted} ORDER BY {order}"
        ).fetchall()
    return result


def verify_existing_copy(source: Path, target: Path) -> None:
    if target.exists() or target.resolve() == source.resolve():
        raise ValueError("Compatibility verification requires a new disposable target")
    # SQLite backup provides a consistent copy even if the source uses WAL.
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as original:
        with sqlite3.connect(target) as copy:
            original.backup(copy)
    with sqlite3.connect(target) as copy:
        before = snapshot(copy)
        if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("Copy failed integrity check")
        if copy.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Copy has orphaned records; adoption refused")
    config = migration_config(f"sqlite:///{target}")
    engine = make_engine(config.attributes["database_url"])
    try:
        with engine.connect() as connection:
            revision = MigrationContext.configure(connection).get_current_revision()
            differences = compare_metadata(
                MigrationContext.configure(connection), Base.metadata
            )
        if not differences:
            with engine.connect() as connection:
                if not ledger_triggers_match(connection):
                    raise RuntimeError(
                        "Financial ledger trigger mismatch; review required, no stamping performed"
                    )
        legacy = MetaData()
        for name in (
            "players",
            "tournaments",
            "matches",
            "tournament_registrations",
            "tournament_results",
            "wallet_transactions",
        ):
            Base.metadata.tables[name].to_metadata(legacy)
        with engine.connect() as connection:
            legacy_differences = compare_metadata(
                MigrationContext.configure(connection), legacy
            )
        pre_financial = MetaData()
        for name, table in Base.metadata.tables.items():
            if name not in ("financial_wallets", "financial_ledger_entries"):
                table.to_metadata(pre_financial)
        with engine.connect() as connection:
            pre_financial_differences = compare_metadata(
                MigrationContext.configure(connection), pre_financial
            )
        supported_baseline = (
            revision in (None, "e20261119db01") and not legacy_differences
        ) or (revision in (None, "f20261120auth") and not pre_financial_differences)
        if differences and not supported_baseline:
            raise RuntimeError(
                "Existing schema differs from ORM; review required, no stamping performed"
            )
        if revision is None:
            try:
                command.upgrade(config, "head")
            except OperationalError:
                print(
                    "Unversioned copy: direct upgrade refused because application tables exist (expected)."
                )
            else:
                raise AssertionError(
                    "Unversioned existing tables unexpectedly upgraded"
                )
            with sqlite3.connect(target) as copy:
                assert snapshot(copy) == before
            print(
                "Explicit verification-only adoption on disposable, schema-matched copy."
            )
            adoption_revision = (
                "head"
                if not differences
                else "e20261119db01" if not legacy_differences else "f20261120auth"
            )
            print(
                f"Explicit disposable-copy stamp: {adoption_revision}; original remains untouched."
            )
            command.stamp(config, adoption_revision)
        command.upgrade(config, "head")
        command.current(config)
        command.check(config)
        with engine.connect() as connection:
            assert ledger_triggers_match(
                connection
            ), "Financial ledger trigger mismatch"
        with sqlite3.connect(target) as copy:
            after = snapshot(copy)
            assert all(
                after[name] == rows for name, rows in before.items()
            ), "Application data changed"
            assert all(
                not rows for name, rows in after.items() if name not in before
            ), "Unexpected migration data"
        print("Existing-copy compatibility passed: all rows and values preserved.")
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--existing-copy-from",
        type=Path,
        help="Read source via SQLite read-only mode; all operations affect only a temporary copy",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(
        prefix="snooker-migration-verification-"
    ) as directory:
        root = Path(directory)
        config = migration_config(f"sqlite:///{root / 'fresh.db'}")
        command.history(config)
        command.heads(config)
        command.current(config)
        command.upgrade(config, "head")
        command.current(config)
        command.check(config)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        command.check(config)
        checked = make_engine(config.attributes["database_url"])
        try:
            with checked.connect() as connection:
                assert ledger_triggers_match(
                    connection
                ), "Financial ledger trigger mismatch"
        finally:
            checked.dispose()
        print(
            "Fresh migration, ORM consistency, ledger triggers, empty downgrade and re-upgrade passed."
        )
        if args.existing_copy_from:
            verify_existing_copy(args.existing_copy_from, root / "existing-copy.db")


if __name__ == "__main__":
    main()
