"""SQLite integrity triggers for new exact-money tables (no legacy-table triggers)."""

from sqlalchemy import DDL, event

TRIGGERS = {
    "financial_ledger_no_update": """CREATE TRIGGER financial_ledger_no_update
        BEFORE UPDATE ON financial_ledger_entries
        BEGIN SELECT RAISE(ABORT, 'Financial ledger is append-only'); END""",
    "financial_ledger_no_delete": """CREATE TRIGGER financial_ledger_no_delete
        BEFORE DELETE ON financial_ledger_entries
        BEGIN SELECT RAISE(ABORT, 'Financial ledger is append-only'); END""",
    "financial_ledger_continuity": """CREATE TRIGGER financial_ledger_continuity
        BEFORE INSERT ON financial_ledger_entries
        BEGIN
          SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM financial_wallets w WHERE w.id = NEW.wallet_id
              AND w.currency = NEW.currency AND w.balance_minor = NEW.balance_after_minor
              AND w.sequence = NEW.sequence
          ) THEN RAISE(ABORT, 'Ledger must match updated wallet') END;
          SELECT CASE WHEN NOT (
            (NEW.sequence = 1 AND NEW.balance_before_minor = 0) OR EXISTS (
              SELECT 1 FROM financial_ledger_entries p WHERE p.wallet_id = NEW.wallet_id
                AND p.sequence = NEW.sequence - 1
                AND p.balance_after_minor = NEW.balance_before_minor
            )
          ) THEN RAISE(ABORT, 'Ledger balance chain is discontinuous') END;
        END""",
}


def attach_ledger_triggers(table) -> None:
    for statement in TRIGGERS.values():
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="sqlite"))


def ledger_triggers_match(connection) -> bool:
    """Fail closed on missing/edited SQLite protections, including unversioned copies."""
    from sqlalchemy import text

    actual = dict(
        connection.execute(
            text(
                "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name='financial_ledger_entries'"
            )
        ).all()
    )
    return all(
        name in actual and " ".join(actual[name].split()) == " ".join(sql.split())
        for name, sql in TRIGGERS.items()
    )
