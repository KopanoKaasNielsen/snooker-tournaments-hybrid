"""Diagnostics never infer currency, quantise, mutate or repair legacy records."""

import sqlite3

import pytest

from scripts.audit_legacy_finances import audit_database


@pytest.fixture
def legacy_copy(tmp_path):
    target = tmp_path / "legacy.db"
    with sqlite3.connect(target) as db:
        db.executescript(
            "CREATE TABLE players(id INTEGER PRIMARY KEY, balance FLOAT NOT NULL);"
            "CREATE TABLE wallet_transactions(id INTEGER PRIMARY KEY, player_id INTEGER, type TEXT, amount FLOAT);"
            "CREATE TABLE tournaments(id INTEGER PRIMARY KEY, entry_fee INTEGER);"
            "CREATE TABLE tournament_registrations(id INTEGER PRIMARY KEY, contribution INTEGER);"
            "INSERT INTO players VALUES (1, 0.3);"
            "INSERT INTO wallet_transactions VALUES (1, 1, 'deposit', 0.1);"
            "INSERT INTO wallet_transactions VALUES (2, 1, 'deposit', 0.2);"
        )
    return target


def test_legacy_diagnostic_sums_decimal_strings_without_rounding_or_mutation(
    legacy_copy,
):
    before = legacy_copy.read_bytes()
    result = audit_database(legacy_copy)
    assert result["findings"] == []
    assert result["currency"] is None and result["conversion_authorized"] is False
    assert result["counts"]["wallet_transactions"] == 2
    assert legacy_copy.read_bytes() == before


def test_legacy_diagnostic_flags_float_drift_without_quantising_it_away(legacy_copy):
    with sqlite3.connect(legacy_copy) as db:
        db.execute("UPDATE players SET balance=?", (0.1 + 0.2,))
    before = legacy_copy.read_bytes()
    assert {f["code"] for f in audit_database(legacy_copy)["findings"]} == {
        "balance_ledger_mismatch"
    }
    assert legacy_copy.read_bytes() == before


@pytest.mark.parametrize("value", [float("inf"), "NaN", "not a number", -1, 0])
def test_legacy_diagnostic_reports_invalid_ledger_amounts(legacy_copy, value):
    with sqlite3.connect(legacy_copy) as db:
        db.execute("UPDATE wallet_transactions SET amount=? WHERE id=1", (value,))
    result = audit_database(legacy_copy)
    assert any(
        f["code"] in {"nonpositive_ledger_amount", "non_finite_or_invalid_amount"}
        for f in result["findings"]
    )


def test_legacy_diagnostic_reports_unknown_types_orphans_and_invalid_fees(legacy_copy):
    with sqlite3.connect(legacy_copy) as db:
        db.execute("INSERT INTO wallet_transactions VALUES (3, 999, 'unknown', 1)")
        db.execute("INSERT INTO tournaments VALUES (1, -1)")
        db.execute("INSERT INTO tournament_registrations VALUES (1, 0.5)")
    codes = {f["code"] for f in audit_database(legacy_copy)["findings"]}
    assert {
        "unknown_transaction_type",
        "orphan_ledger",
        "invalid_legacy_integer_amount",
    } <= codes


def test_legacy_diagnostic_never_creates_missing_database(tmp_path):
    target = tmp_path / "must_not_exist.db"
    with pytest.raises(sqlite3.OperationalError):
        audit_database(target)
    assert not target.exists()
