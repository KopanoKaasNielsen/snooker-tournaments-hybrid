"""Explicit development setup. Production uses reviewed Alembic migrations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from app.database import SessionLocal, engine, get_database_url

ROOT = Path(__file__).resolve().parents[1]


def migration_config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


def require_development_database() -> None:
    if os.environ.get("APP_ENV") != "development" or not os.environ.get("DATABASE_URL"):
        raise ValueError(
            "Set APP_ENV=development and an explicit DATABASE_URL for demo setup"
        )
    url = make_url(get_database_url())
    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or url.database == ":memory:"
    ):
        raise ValueError("Development setup requires an explicit SQLite file")
    if Path(url.database).resolve() == (ROOT / "snooker.db").resolve():
        raise ValueError("Development setup refuses the existing repository snooker.db")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "seed-demo"])
    parser.add_argument(
        "--confirm-demo", action="store_true", help="Acknowledge demo record insertion"
    )
    args = parser.parse_args()
    try:
        require_development_database()
        config = migration_config(get_database_url())
        if args.command == "init":
            command.upgrade(config, "head")
            print("Development schema migrated; no demo data inserted.")
        else:
            if not args.confirm_demo:
                raise ValueError("Demo seeding requires --confirm-demo")
            with engine.connect() as connection:
                current = MigrationContext.configure(connection).get_current_heads()
            if set(current) != set(ScriptDirectory.from_config(config).get_heads()):
                raise ValueError(
                    "Migrate the development database to head before seeding"
                )
            from app.init_db import seed_data

            seed_data(SessionLocal)
            print("Demo seed complete (existing named records preserved).")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
