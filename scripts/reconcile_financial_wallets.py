"""Read-only exact BWP subledger reconciliation; no adoption, posting or repair."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys

from sqlalchemy import event
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from app.database import make_engine
from app.services.financial_wallets import FinancialError, FinancialWalletService


def inspect_database(source: Path) -> dict:
    url = URL.create(
        "sqlite",
        database=source.resolve().as_uri(),
        query={"mode": "ro", "uri": "true"},
    )
    engine = make_engine(url.render_as_string())

    @event.listens_for(engine, "connect")
    def read_only(connection, record):
        connection.execute("PRAGMA query_only=ON")

    try:
        reports = FinancialWalletService(engine).reconcile()
        with engine.connect() as db:
            integrity_ok = db.exec_driver_sql("PRAGMA integrity_check").fetchall() == [
                ("ok",)
            ]
            foreign_keys_ok = not db.exec_driver_sql(
                "PRAGMA foreign_key_check"
            ).fetchall()
        return {
            "read_only": True,
            "currency": "BWP",
            "historical_adoption": False,
            "integrity_ok": integrity_ok,
            "foreign_keys_ok": foreign_keys_ok,
            "consistent": integrity_ok
            and foreign_keys_ok
            and all(r.consistent for r in reports),
            "wallets": [{**asdict(r), "consistent": r.consistent} for r in reports],
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect_database(args.database)
    except (SQLAlchemyError, FinancialError, sqlite3.Error, OSError):
        print(
            "Unable to inspect exact-money schema read-only; migrate only an approved disposable database",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["consistent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
