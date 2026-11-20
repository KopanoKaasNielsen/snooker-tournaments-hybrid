"""Read-only legacy money diagnostics; never assign currency, round or repair values."""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, localcontext
import json
from pathlib import Path
import sqlite3
import sys


@dataclass(frozen=True)
class Finding:
    code: str
    table: str
    record_id: int


def audit_database(source: Path) -> dict:
    """Inspect a consistent read-only SQLite snapshot without importing application code."""
    findings: list[Finding] = []
    with closing(
        sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        integrity_ok = db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        foreign_keys_ok = not db.execute("PRAGMA foreign_key_check").fetchall()
        players = db.execute("SELECT id, balance FROM players ORDER BY id").fetchall()
        ledger = db.execute(
            "SELECT id, player_id, type, amount FROM wallet_transactions ORDER BY id"
        ).fetchall()
        fees = db.execute(
            "SELECT id, entry_fee FROM tournaments ORDER BY id"
        ).fetchall()
        contributions = db.execute(
            "SELECT id, contribution FROM tournament_registrations ORDER BY id"
        ).fetchall()

    def number(value, table: str, record_id: int) -> Decimal | None:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            result = Decimal("NaN")
        if not result.is_finite():
            findings.append(Finding("non_finite_or_invalid_amount", table, record_id))
            return None
        return result

    balances = {}
    for player_id, value in players:
        balance = number(value, "players", player_id)
        if balance is not None and balance < 0:
            findings.append(Finding("negative_balance", "players", player_id))
        balances[player_id] = balance
    totals = dict.fromkeys(balances, Decimal(0))
    invalid_ledgers = set()
    signs = {"deposit": 1, "prize": 1, "withdrawal": -1, "fee": -1}
    # SQLite floats can span 308 decimal digits; diagnostics must not round their sums.
    with localcontext() as context:
        context.prec = 1000
        for record_id, player_id, kind, value in ledger:
            amount = number(value, "wallet_transactions", record_id)
            if player_id not in balances:
                findings.append(
                    Finding("orphan_ledger", "wallet_transactions", record_id)
                )
            if kind not in signs:
                findings.append(
                    Finding(
                        "unknown_transaction_type", "wallet_transactions", record_id
                    )
                )
            if amount is not None and amount <= 0:
                findings.append(
                    Finding(
                        "nonpositive_ledger_amount", "wallet_transactions", record_id
                    )
                )
            if amount is None or amount <= 0 or kind not in signs:
                invalid_ledgers.add(player_id)
            elif player_id in totals:
                totals[player_id] += signs[kind] * amount
        for player_id, balance in balances.items():
            if balance is None or player_id in invalid_ledgers:
                continue
            if balance != totals[player_id]:
                findings.append(
                    Finding("balance_ledger_mismatch", "players", player_id)
                )
    for table, records in (
        ("tournaments", fees),
        ("tournament_registrations", contributions),
    ):
        for record_id, value in records:
            amount = number(value, table, record_id)
            if amount is not None and (
                amount < 0 or amount != amount.to_integral_value()
            ):
                findings.append(
                    Finding("invalid_legacy_integer_amount", table, record_id)
                )
    return {
        "read_only": True,
        "currency": None,
        "conversion_authorized": False,
        "integrity_ok": integrity_ok,
        "foreign_keys_ok": foreign_keys_ok,
        "counts": {
            "players": len(players),
            "wallet_transactions": len(ledger),
            "tournaments": len(fees),
            "tournament_registrations": len(contributions),
        },
        "findings": [asdict(finding) for finding in findings],
        "limitations": [
            "Currency and original decimal intent are unknown; no rounding or repair performed.",
            "Matching balances do not prove external settlement or complete financial history.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit_database(args.database)
    except (sqlite3.Error, OSError) as exc:
        print(f"Read-only financial audit failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return int(
        bool(result["findings"])
        or not result["integrity_ok"]
        or not result["foreign_keys_ok"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
