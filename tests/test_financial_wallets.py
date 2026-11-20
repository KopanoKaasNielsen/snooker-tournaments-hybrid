from decimal import Decimal
from threading import Event, Thread, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, make_engine
from app.models import FinancialLedgerEntry, FinancialWallet, Player, WalletTransaction
from app.money import MAX_MINOR, InvalidMoney
from app.services import wallet as legacy_wallet
from app.services.financial_wallets import (
    FinancialWalletService,
    FinancialError,
    FinancialBusy,
    IdempotencyConflict,
    InsufficientFunds,
    LegacyAdoptionRequired,
    Receipt,
)


@pytest.fixture
def finance(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'financial.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        player = Player(name="Exact wallet player")
        db.add(player)
        db.commit()
        pid = player.id
    service = FinancialWalletService(engine)
    account = service.open_wallet(pid, currency="BWP")
    yield service, engine, account, sessions
    engine.dispose()


def post(service, account, value="1.00", kind="deposit", key=None):
    return service.post(
        account.id,
        kind=kind,
        amount=Decimal(value),
        currency="BWP",
        idempotency_key=key or str(uuid4()),
    )


def test_exact_posting_and_signed_reconciliation_do_not_change_legacy_records(finance):
    service, _, account, sessions = finance
    post(service, account, "0.10")
    post(service, account, "0.20")
    post(service, account, "0.01", "withdrawal")
    post(service, account, "0.02", "fee")
    receipt = post(service, account, "0.03", "prize")
    assert receipt.balance_after == Decimal("0.30")
    report = service.reconcile()[0]
    assert report.consistent and report.balance == report.ledger_balance == Decimal(
        "0.30"
    )
    assert report.entry_count == 5
    with sessions() as db:
        wallet = db.get(FinancialWallet, account.id)
        assert wallet.balance_minor == 30 and wallet.sequence == 5
        assert db.get(Player, account.player_id).balance == 0
        assert db.query(WalletTransaction).count() == 0


def test_open_wallet_is_repeatable_but_never_adopts_existing_money(finance):
    service, _, account, sessions = finance
    assert service.open_wallet(account.player_id, currency="BWP") == account
    with sessions() as db:
        player = Player(name="Historical money", balance=12.345)
        db.add(player)
        db.commit()
        pid = player.id
    with pytest.raises(LegacyAdoptionRequired):
        service.open_wallet(pid, currency="BWP")
    with sessions() as db:
        assert db.get(Player, pid).balance == 12.345
        assert db.query(FinancialWallet).count() == 1


def test_net_zero_legacy_history_also_requires_adoption(finance):
    service, _, _, sessions = finance
    with sessions() as db:
        player = Player(name="Historical net zero")
        db.add(player)
        db.commit()
        pid = player.id
        legacy_wallet.deposit(db, pid, 1)
        legacy_wallet.withdraw(db, pid, 1)
    with pytest.raises(LegacyAdoptionRequired):
        service.open_wallet(pid, currency="BWP")


def test_legacy_adapter_cannot_write_into_an_exact_wallet(finance):
    _, _, account, sessions = finance
    with sessions() as db, pytest.raises(ValueError, match="Legacy writes"):
        legacy_wallet.deposit(db, account.player_id, 1)
    with sessions() as db:
        assert db.get(Player, account.player_id).balance == 0
        assert db.query(WalletTransaction).count() == 0


def test_legacy_activity_after_opening_is_reported_and_blocks_new_posting(finance):
    service, _, account, sessions = finance
    with sessions() as db:
        db.get(Player, account.player_id).balance = 1.25
        db.commit()
    with pytest.raises(LegacyAdoptionRequired):
        post(service, account)
    assert service.reconcile()[0].issues == ("legacy_activity_requires_review",)


def test_idempotent_retry_returns_original_receipt_not_latest_balance(finance):
    service, _, account, sessions = finance
    key = str(uuid4())
    original = post(service, account, key=key)
    post(service, account, "0.50", "withdrawal")
    assert post(service, account, key=key) == original
    assert original.balance_after == Decimal("1.00")
    assert service.reconcile()[0].balance == Decimal("0.50")
    with sessions() as db:
        assert db.query(FinancialLedgerEntry).count() == 2


@pytest.mark.parametrize("kind,value", [("deposit", "2.00"), ("withdrawal", "1.00")])
def test_idempotency_key_payload_conflicts_never_post_again(finance, kind, value):
    service, _, account, _ = finance
    key = str(uuid4())
    post(service, account, key=key)
    with pytest.raises(IdempotencyConflict):
        post(service, account, value, kind, key)
    assert service.reconcile()[0].entry_count == 1


def test_idempotency_key_scope_is_global_across_wallets(finance):
    service, _, account, sessions = finance
    with sessions() as db:
        player = Player(name="Other exact wallet")
        db.add(player)
        db.commit()
        pid = player.id
    other = service.open_wallet(pid, currency="BWP")
    key = str(uuid4())
    post(service, account, key=key)
    with pytest.raises(IdempotencyConflict):
        post(service, other, key=key)
    assert sorted(report.entry_count for report in service.reconcile()) == [0, 1]


@pytest.mark.parametrize(
    "key",
    [
        None,
        "",
        "not-a-uuid",
        str(uuid4()).upper(),
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_posting_requires_canonical_uuid4(finance, key):
    service, _, account, _ = finance
    with pytest.raises(FinancialError, match="UUID4"):
        service.post(
            account.id,
            kind="deposit",
            amount=Decimal("1"),
            currency="BWP",
            idempotency_key=key,
        )
    assert service.reconcile()[0].entry_count == 0


def test_insufficient_funds_and_balance_overflow_leave_no_ledger_side_effect(finance):
    service, _, account, _ = finance
    with pytest.raises(InsufficientFunds):
        post(service, account, "0.01", "withdrawal")
    post(service, account, "90000000000000.00")
    with pytest.raises(FinancialError, match="limit"):
        post(service, account, "0.01")
    report = service.reconcile()[0]
    assert report.consistent and report.entry_count == 1
    assert report.balance == Decimal("90000000000000.00")


def test_ledger_insert_failure_rolls_back_balance_sequence_and_retry_key(finance):
    service, engine, account, sessions = finance
    key = str(uuid4())

    def fail_insert(connection, cursor, statement, parameters, context, many):
        if (
            statement.lstrip()
            .lower()
            .startswith("insert into financial_ledger_entries")
        ):
            raise RuntimeError("Injected ledger insert failure")

    event.listen(engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="Injected ledger"):
            post(service, account, key=key)
    finally:
        event.remove(engine, "before_cursor_execute", fail_insert)
    report = service.reconcile()[0]
    assert report.consistent and report.balance == 0 and report.entry_count == 0
    assert post(service, account, key=key).sequence == 1
    assert engine.pool.checkedout() == 0


def test_commit_failure_rolls_back_flushed_balance_and_ledger(finance):
    service, _, account, _ = finance

    def fail_commit(db):
        raise RuntimeError("Injected commit failure")

    event.listen(Session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="commit failure"):
            post(service, account)
    finally:
        event.remove(Session, "before_commit", fail_commit)
    report = service.reconcile()[0]
    assert report.consistent and report.entry_count == 0 and report.balance == 0


def test_service_does_not_commit_a_callers_unrelated_session(finance):
    service, _, account, sessions = finance
    with sessions() as caller:
        pending = Player(name="Caller work must stay uncommitted")
        caller.add(pending)
        post(service, account)
        assert pending in caller.new
        with sessions() as independent:
            assert (
                independent.scalar(select(Player.id).where(Player.name == pending.name))
                is None
            )


def test_reconciliation_detects_tampering_and_does_not_repair_it(finance):
    service, _, account, sessions = finance
    post(service, account)
    with sessions() as db:
        db.execute(
            update(FinancialWallet)
            .where(FinancialWallet.id == account.id)
            .values(balance_minor=200)
        )
        db.commit()
    report = service.reconcile()[0]
    assert report.issues == ("balance_ledger_mismatch",)
    assert report.balance == Decimal("2.00") and report.ledger_balance == Decimal(
        "1.00"
    )
    with pytest.raises(IntegrityError, match="discontinuous"):
        post(service, account)
    with sessions() as db:
        assert db.get(FinancialWallet, account.id).balance_minor == 200
        assert db.query(FinancialLedgerEntry).count() == 1


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_ledger_is_append_only_even_for_raw_database_writes(finance, operation):
    service, _, account, sessions = finance
    receipt = post(service, account)
    with sessions() as db:
        statement = (
            update(FinancialLedgerEntry).values(id=str(uuid4()))
            if operation == "update"
            else delete(FinancialLedgerEntry)
        )
        with pytest.raises(IntegrityError, match="append-only"):
            db.execute(statement)
        db.rollback()
        assert db.get(FinancialLedgerEntry, receipt.id) is not None


@pytest.mark.parametrize(
    "column,value",
    [
        ("amount_minor", 0),
        ("amount_minor", -1),
        ("amount_minor", 0.5),
        ("amount_minor", float("inf")),
        ("amount_minor", MAX_MINOR + 1),
        ("kind", "unknown"),
        ("currency", "USD"),
        ("idempotency_key", "bad-key"),
        ("balance_before_minor", -1),
        ("balance_after_minor", -1),
        ("sequence", 0),
    ],
)
def test_ledger_constraints_reject_invalid_storage_atomically(finance, column, value):
    _, _, account, sessions = finance
    values = dict(
        id=str(uuid4()),
        idempotency_key=str(uuid4()),
        wallet_id=account.id,
        currency="BWP",
        kind="deposit",
        amount_minor=100,
        balance_before_minor=0,
        balance_after_minor=100,
        sequence=1,
    )
    values[column] = value
    with pytest.raises(IntegrityError):
        with sessions() as db, db.begin():
            db.execute(
                update(FinancialWallet)
                .where(FinancialWallet.id == account.id)
                .values(balance_minor=100, sequence=1)
            )
            db.add(FinancialLedgerEntry(**values))
            db.flush()
    with sessions() as db:
        assert db.get(FinancialWallet, account.id).balance_minor == 0
        assert db.query(FinancialLedgerEntry).count() == 0


@pytest.mark.parametrize(
    "column,value",
    [
        ("balance_minor", -1),
        ("balance_minor", 0.5),
        ("balance_minor", MAX_MINOR + 1),
        ("balance_minor", float("inf")),
        ("balance_minor", 100),
        ("sequence", -1),
        ("sequence", 0.5),
        ("currency", "USD"),
    ],
)
def test_wallet_database_checks_prevent_invalid_or_unfunded_storage(
    finance, column, value
):
    _, _, account, sessions = finance
    with sessions() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                update(FinancialWallet)
                .where(FinancialWallet.id == account.id)
                .values({column: value})
            )
            db.commit()
        db.rollback()
        assert db.get(FinancialWallet, account.id).balance_minor == 0


def test_wallet_foreign_key_and_unique_player_are_enforced(finance):
    _, _, account, sessions = finance
    for pid in (999999, account.player_id):
        with sessions() as db:
            db.add(FinancialWallet(id=str(uuid4()), player_id=pid, currency="BWP"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()


def _ordered_race(
    engine, first_fn, second_fn, update_marker="update financial_wallets"
):
    """Hold writer one, observe independent writer two's BEGIN, then release; no sleeps."""
    held, release, contender = Event(), Event(), Event()
    results, connections = {}, {}

    def hook(connection, cursor, statement, parameters, context, many):
        name = current_thread().name
        sql = statement.lower().lstrip()
        if sql == "begin immediate":
            connections[name] = id(connection.connection.driver_connection)
            if name == "financial-second":
                contender.set()
        if name == "financial-first" and sql.startswith(update_marker):
            held.set()
            if not release.wait(15):
                raise RuntimeError("Test writer reservation timed out")

    def run(label, function):
        try:
            results[label] = function()
        except Exception as error:
            results[label] = error

    first = Thread(name="financial-first", target=run, args=("first", first_fn))
    second = Thread(name="financial-second", target=run, args=("second", second_fn))
    event.listen(engine, "before_cursor_execute", hook)
    try:
        first.start()
        assert held.wait(10), "First writer did not acquire its reservation"
        second.start()
        assert contender.wait(10), "Second connection did not attempt BEGIN IMMEDIATE"
        release.set()
        first.join(15)
        second.join(15)
        assert not first.is_alive() and not second.is_alive()
        assert connections["financial-first"] != connections["financial-second"]
    finally:
        release.set()
        first.join(15)
        if second.ident is not None:
            second.join(15)
        event.remove(engine, "before_cursor_execute", hook)
    return results


def test_concurrent_withdrawals_cannot_overspend_or_diverge_from_ledger(finance):
    service, engine, account, _ = finance
    post(service, account, "100")
    results = _ordered_race(
        engine,
        lambda: post(service, account, "80", "withdrawal"),
        lambda: post(service, account, "80", "withdrawal"),
    )
    assert isinstance(results["first"], Receipt)
    assert isinstance(results["second"], InsufficientFunds)
    report = service.reconcile()[0]
    assert report.consistent and report.balance == report.ledger_balance == Decimal(
        "20.00"
    )
    assert report.entry_count == 2


def test_concurrent_identical_retries_create_exactly_one_receipt(finance):
    service, engine, account, _ = finance
    key = str(uuid4())
    results = _ordered_race(
        engine,
        lambda: post(service, account, key=key),
        lambda: post(service, account, key=key),
    )
    assert isinstance(results["first"], Receipt)
    assert results["first"] == results["second"]
    assert service.reconcile()[0].entry_count == 1


def test_concurrent_credits_are_not_lost(finance):
    service, engine, account, _ = finance
    results = _ordered_race(
        engine,
        lambda: post(service, account, "0.10"),
        lambda: post(service, account, "0.20"),
    )
    assert all(isinstance(value, Receipt) for value in results.values())
    report = service.reconcile()[0]
    assert (
        report.consistent
        and report.balance == Decimal("0.30")
        and report.entry_count == 2
    )


def test_concurrent_conflicting_retry_is_rejected(finance):
    service, engine, account, _ = finance
    key = str(uuid4())
    results = _ordered_race(
        engine,
        lambda: post(service, account, "1", key=key),
        lambda: post(service, account, "2", key=key),
    )
    assert isinstance(results["second"], IdempotencyConflict)
    assert service.reconcile()[0].balance == Decimal("1.00")


def test_legacy_cached_sessions_now_refresh_before_withdrawal(finance):
    _, _, _, sessions = finance
    with sessions() as db:
        player = Player(name="Legacy stale session regression")
        db.add(player)
        db.commit()
        pid = player.id
        legacy_wallet.deposit(db, pid, 100.0)
    with sessions() as first, sessions() as second:
        cached_first, cached_second = first.get(Player, pid), second.get(Player, pid)
        assert cached_first.balance == cached_second.balance == 100
        legacy_wallet.withdraw(first, pid, 80.0)
        with pytest.raises(ValueError, match="Insufficient balance"):
            legacy_wallet.withdraw(second, pid, 80.0)
    with sessions() as db:
        assert db.get(Player, pid).balance == 20.0
        assert (
            sum(
                row.amount if row.type.value == "deposit" else -row.amount
                for row in db.query(WalletTransaction)
            )
            == 20.0
        )


def test_legacy_concurrent_cached_withdrawals_are_serialised(finance):
    _, engine, _, sessions = finance
    with sessions() as db:
        player = Player(name="Legacy concurrent regression")
        db.add(player)
        db.commit()
        pid = player.id
        legacy_wallet.deposit(db, pid, 100.0)
    starting = []

    def withdraw():
        with sessions() as db:
            cached = db.get(Player, pid)
            starting.append(cached.balance)
            return legacy_wallet.withdraw(db, pid, 80.0).balance

    results = _ordered_race(engine, withdraw, withdraw, update_marker="update players")
    assert starting == [100.0, 100.0]
    assert results["first"] == 20.0
    assert isinstance(results["second"], ValueError) and "Insufficient" in str(
        results["second"]
    )
    with sessions() as db:
        assert db.get(Player, pid).balance == 20.0
        assert db.query(WalletTransaction).count() == 2


def test_busy_writer_fails_without_partial_post_and_same_key_can_retry(finance):
    service, engine, account, _ = finance

    def short_timeout(connection, record, proxy):
        connection.execute("PRAGMA busy_timeout=1")

    event.listen(engine, "checkout", short_timeout)
    key = str(uuid4())
    try:
        with engine.connect() as blocker:
            blocker.exec_driver_sql("BEGIN IMMEDIATE")
            with pytest.raises(FinancialBusy):
                post(service, account, key=key)
            blocker.rollback()
    finally:
        event.remove(engine, "checkout", short_timeout)
    assert post(service, account, key=key).sequence == 1
    assert service.reconcile()[0].consistent


def test_read_only_reconciliation_cli_preserves_database_and_handles_missing_source(
    finance, tmp_path
):
    from pathlib import Path
    from sqlalchemy.exc import OperationalError
    from scripts.reconcile_financial_wallets import inspect_database

    service, engine, account, _ = finance
    post(service, account, "0.30")
    source = Path(engine.url.database)
    before = source.read_bytes()
    result = inspect_database(source)
    assert (
        result["consistent"]
        and result["read_only"]
        and not result["historical_adoption"]
    )
    assert result["wallets"][0]["balance"] == Decimal("0.30")
    assert source.read_bytes() == before
    missing = tmp_path / "must_not_create.db"
    with pytest.raises(OperationalError):
        inspect_database(missing)
    assert not missing.exists()


def test_database_idempotency_constraint_rolls_back_a_duplicate_key(finance):
    service, _, account, sessions = finance
    original = post(service, account)
    with pytest.raises(IntegrityError, match="UNIQUE"):
        with sessions() as db, db.begin():
            db.execute(
                update(FinancialWallet)
                .where(FinancialWallet.id == account.id)
                .values(balance_minor=200, sequence=2)
            )
            db.add(
                FinancialLedgerEntry(
                    id=str(uuid4()),
                    idempotency_key=original.idempotency_key,
                    wallet_id=account.id,
                    currency="BWP",
                    kind="deposit",
                    amount_minor=100,
                    balance_before_minor=100,
                    balance_after_minor=200,
                    sequence=2,
                )
            )
            db.flush()
    report = service.reconcile()[0]
    assert (
        report.consistent
        and report.entry_count == 1
        and report.balance == Decimal("1.00")
    )


def test_database_rejects_discontinuous_but_individually_balanced_entry(finance):
    service, _, account, sessions = finance
    post(service, account)
    with pytest.raises(IntegrityError, match="discontinuous"):
        with sessions() as db, db.begin():
            db.execute(
                update(FinancialWallet)
                .where(FinancialWallet.id == account.id)
                .values(balance_minor=200, sequence=2)
            )
            db.add(
                FinancialLedgerEntry(
                    id=str(uuid4()),
                    idempotency_key=str(uuid4()),
                    wallet_id=account.id,
                    currency="BWP",
                    kind="deposit",
                    amount_minor=150,
                    balance_before_minor=50,
                    balance_after_minor=200,
                    sequence=2,
                )
            )
            db.flush()
    assert service.reconcile()[0].consistent


def test_preserved_original_database_is_refused_before_any_connection():
    from pathlib import Path
    from sqlalchemy.engine import URL

    root = Path(__file__).resolve().parents[1] / "snooker.db"
    for url in (
        f"sqlite:///{root}",
        URL.create(
            "sqlite", database=root.as_uri(), query={"uri": "true", "mode": "rw"}
        ).render_as_string(),
    ):
        protected = make_engine(url)
        try:
            with pytest.raises(FinancialError, match="preserved repository database"):
                FinancialWalletService(protected).open_wallet(1, currency="BWP")
            assert protected.pool.checkedout() == 0
        finally:
            protected.dispose()


def test_postgresql_foundation_is_explicitly_unsupported():
    from sqlalchemy import create_mock_engine

    engine = create_mock_engine("postgresql://", lambda *args: None)
    with pytest.raises(FinancialError, match="SQLite only"):
        FinancialWalletService(engine)


def test_invalid_operations_leave_account_unchanged(finance):
    service, _, account, _ = finance
    for kind, currency, amount in (
        ("unknown", "BWP", Decimal("1")),
        ("deposit", "USD", Decimal("1")),
        ("deposit", "BWP", Decimal("0.001")),
    ):
        with pytest.raises((FinancialError, InvalidMoney)):
            service.post(
                account.id,
                kind=kind,
                currency=currency,
                amount=amount,
                idempotency_key=str(uuid4()),
            )
    assert service.reconcile()[0].consistent and service.reconcile()[0].entry_count == 0


def test_legacy_ledger_failure_rolls_back_balance_and_closes_failed_unit(finance):
    _, engine, _, sessions = finance
    with sessions() as db:
        player = Player(name="Legacy rollback regression")
        db.add(player)
        db.commit()
        pid = player.id

    def reject_ledger(connection, cursor, statement, parameters, context, many):
        if statement.lower().lstrip().startswith("insert into wallet_transactions"):
            raise RuntimeError("Injected legacy ledger failure")

    event.listen(engine, "before_cursor_execute", reject_ledger)
    try:
        with (
            sessions() as db,
            pytest.raises(RuntimeError, match="legacy ledger failure"),
        ):
            legacy_wallet.deposit(db, pid, 100.0)
    finally:
        event.remove(engine, "before_cursor_execute", reject_ledger)
    with sessions() as db:
        assert db.get(Player, pid).balance == 0
        assert db.query(WalletTransaction).count() == 0
        legacy_wallet.deposit(db, pid, 1)
        assert db.get(Player, pid).balance == 1


def test_service_fails_closed_if_integrity_trigger_is_missing(finance):
    service, engine, account, sessions = finance
    with engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER financial_ledger_no_update")
    with pytest.raises(FinancialError, match="triggers are missing or changed"):
        post(service, account)
    with pytest.raises(FinancialError, match="triggers are missing or changed"):
        service.reconcile()
    with sessions() as db:
        assert db.get(FinancialWallet, account.id).balance_minor == 0
        assert db.query(FinancialLedgerEntry).count() == 0


def test_unversioned_copy_missing_ledger_trigger_is_not_stamped(finance, tmp_path):
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    from scripts.verify_migrations import verify_existing_copy

    _, engine, _, _ = finance
    with engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER financial_ledger_no_delete")
    source = Path(engine.url.database)
    before = source.read_bytes()
    target = tmp_path / "unsafe-copy.db"
    with pytest.raises(RuntimeError, match="trigger mismatch"):
        verify_existing_copy(source, target)
    assert source.read_bytes() == before
    with closing(sqlite3.connect(target)) as db:
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE name='alembic_version'"
            ).fetchall()
            == []
        )
