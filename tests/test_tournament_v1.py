"""Inactive V1 review workflows. Test evidence adapters exist only in tests."""

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
import json

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError

from tests.test_financial_operations import ops, password_hash, posted, request, verify
from tests.test_financial_wallets import _ordered_race
from app.models import (
    Tournament,
    TournamentV1Policy,
    TournamentPoolAccount,
    TournamentV1Record,
    TournamentRegistration,
    FinancialOperation,
    FinancialLedgerEntry,
    Match,
    User,
)
from app.services.tournament_v1 import TournamentV1Service
from app.services.tournament_financials import TournamentPolicyRequired
from app.services.financial_operations import OperationDenied, OperationConflict
from app.services.financial_wallets import FinancialError
from app.tournament_prize_preview import (
    allocate_preview,
    preview_token_basis,
    PreviewWinner,
)
from app.money import InvalidMoney
from app.time import utc_now
from app import crud, schemas


def key():
    return str(uuid4())


EVIDENCE = "a" * 64


@pytest.fixture
def v1(ops):
    ops.v1 = TournamentV1Service(ops.engine)
    ops.deadline = utc_now() + timedelta(days=1)
    ops.starts = utc_now() + timedelta(days=2)
    return ops


def create(f, price=100, capacity=4, **kwargs):
    return f.v1.create_tournament(
        f.organiser.token,
        name=kwargs.pop("name", key()),
        price_minor=price,
        currency=kwargs.pop("currency", "BWP"),
        capacity=capacity,
        registration_deadline=f.deadline,
        commences_at=f.starts,
        idempotency_key=kwargs.pop("idempotency_key", key()),
        **kwargs,
    )


def register(f, p, actor=None):
    actor = actor or f.owner
    f.v1.approve_eligibility(
        f.organiser.token, p, actor.id, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    return f.v1.register(actor.token, p, idempotency_key=key())


def rows(f, p, kind):
    with f.sessions() as db:
        return db.scalars(
            select(TournamentV1Record).where(
                TournamentV1Record.policy_id == p, TournamentV1Record.kind == kind
            )
        ).all()


def fee_reference(f, p):
    reg = register(f, p)
    obligation = rows(f, p, "FEE_OBLIGATION")[0]
    posted(f, amount="10")
    fee = request(f, actor=f.admin, amount="1", kind="fee")
    verify(f, fee, actor=f.checker)
    f.service.post(f.checker.token, fee.id)
    ref = f.v1.review_posted_fee_reference(
        f.checker.token, p, obligation.id, fee.id, idempotency_key=key()
    )
    return reg, ref, fee


def finished(f, monkeypatch, count=2):
    p = create(f, price=0)
    actors = [f.owner, f.other, f.checker][:count]
    for actor in actors:
        register(f, p, actor)
    # At least two independent players, with explicit staff-created knockout matches.
    mids = []
    if count == 3:
        mids.append(
            f.v1.create_match(
                f.organiser.token,
                p,
                actors[0].pid,
                actors[2].pid,
                idempotency_key=key(),
            )
        )
    if count >= 2:
        mids.append(
            f.v1.create_match(
                f.organiser.token,
                p,
                actors[0].pid,
                actors[1].pid,
                idempotency_key=key(),
            )
        )
    monkeypatch.setattr(
        "app.services.tournament_v1.utc_now", lambda: f.starts + timedelta(seconds=1)
    )
    for mid in mids:
        f.v1.submit_result(
            f.organiser.token,
            p,
            mid,
            2,
            0,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    rev = f.v1.lock_results(
        f.organiser.token,
        p,
        [a.pid for a in actors],
        final_match_id=mids[-1] if mids else None,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    return p, rev, mids


def test_exact_preview_conservation_normalisation_and_odd_thebe():
    for n in (1, 2, 3):
        winners = tuple(PreviewWinner(i, i) for i in range(1, n + 1))
        for amount in (*range(101), 9000000000000000):
            out = allocate_preview(amount, winners, currency="BWP")
            assert sum(s.amount_minor for s in out.shares) == amount
            assert all(
                type(s.amount_minor) is int and s.amount_minor >= 0 for s in out.shares
            )
            assert not out.postable and out.token_state == "UNRESOLVED"
    three = tuple(PreviewWinner(i, i) for i in (1, 2, 3))
    assert [
        s.amount_minor for s in allocate_preview(5, three, currency="BWP").shares
    ] == [3, 2, 0]
    assert [
        s.amount_minor for s in allocate_preview(1, three[:2], currency="BWP").shares
    ] == [1, 0]
    assert [
        s.amount_minor for s in allocate_preview(101, three, currency="BWP").shares
    ] == [61, 30, 10]
    for amount in (-1, True, 1.1, Decimal("1"), 9000000000000001):
        with pytest.raises(InvalidMoney):
            allocate_preview(amount, three, currency="BWP")
    for winners in (
        (),
        (PreviewWinner(1, 1), PreviewWinner(1, 2)),
        (PreviewWinner(1, 2),),
        tuple(PreviewWinner(i, i) for i in range(1, 5)),
    ):
        with pytest.raises(ValueError):
            allocate_preview(100, winners, currency="BWP")
    with pytest.raises(InvalidMoney):
        allocate_preview(1, three, currency="USD")
    scenario = preview_token_basis(101, three, currency="BWP")
    assert (
        scenario.prize_preview is None
        and scenario.unresolved_deduction_basis.numerator == 101
    )
    assert (
        scenario.actual_deduction_minor
        is scenario.token_units
        is scenario.token_asset
        is None
    )
    assert not scenario.postable
    assert (
        sum(
            s.amount_minor
            for s in preview_token_basis(
                100, three, currency="BWP"
            ).prize_preview.shares
        )
        == 90
    )


def test_policy_is_opt_in_immutable_and_creation_idempotent(v1):
    f = v1
    k = key()
    p = create(f, name="Explicit V1", idempotency_key=k)
    assert create(f, name="Explicit V1", idempotency_key=k) == p
    with pytest.raises(OperationConflict):
        create(f, name="Different", idempotency_key=k)
    with f.sessions() as db:
        policy = db.get(TournamentV1Policy, p)
        legacy = Tournament(name="Legacy isolation", entry_fee=71)
        db.add(legacy)
        db.commit()
        assert db.query(TournamentV1Policy).count() == 1
        assert (
            policy.version == "BWP_TOURNAMENT_V1"
            and policy.activation_state == "INACTIVE"
        )
        assert policy.token_state == "UNRESOLVED" and policy.price_minor == 100
        assert db.get(Tournament, policy.tournament_id).entry_fee == 0
        with pytest.raises(IntegrityError, match="immutable"):
            db.execute(
                text("UPDATE tournament_v1_policies SET price_minor=200 WHERE id=:id"),
                {"id": p},
            )
        db.rollback()
        with pytest.raises(IntegrityError, match="immutable"):
            db.execute(
                text("DELETE FROM tournament_pool_accounts WHERE policy_id=:id"),
                {"id": p},
            )
    for value in (-1, True, Decimal("1.00"), 1.5):
        with pytest.raises(InvalidMoney):
            create(f, price=value)
    with pytest.raises(InvalidMoney):
        create(f, currency="ZAR")
    with pytest.raises(OperationDenied):
        f.v1.create_tournament(
            f.owner.token,
            name="Forbidden",
            price_minor=0,
            currency="BWP",
            capacity=1,
            registration_deadline=f.deadline,
            commences_at=f.starts,
            idempotency_key=key(),
        )


def test_owner_consent_fee_identity_free_and_waived_zero_funding(v1):
    f = v1
    p = create(f)
    with pytest.raises(OperationDenied):
        f.v1.register(f.owner.token, p, idempotency_key=key())
    reg = register(f, p)
    assert f.v1.register(f.owner.token, p, idempotency_key=key()) == reg
    assert len(rows(f, p, "REGISTRATION")) == len(rows(f, p, "FEE_OBLIGATION")) == 1
    assert not rows(f, p, "CONFIRMATION")
    with pytest.raises(TournamentPolicyRequired):
        f.v1.monetary_action(f.admin.token, p)
    with pytest.raises(HTTPException):
        f.v1.approve_waiver(
            f.owner.token, p, reg, evidence_digest=EVIDENCE, idempotency_key=key()
        )
    waiver = f.v1.approve_waiver(
        f.admin.token, p, reg, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    assert (
        f.v1.approve_waiver(
            f.checker.token, p, reg, evidence_digest=EVIDENCE, idempotency_key=key()
        )
        == waiver
    )
    assert json.loads(rows(f, p, "CONFIRMATION")[0].data_json)["basis"] == "WAIVER"
    free = create(f, price=0)
    register(f, free)
    assert rows(f, free, "FEE_OBLIGATION")[0].amount_minor == 0
    assert json.loads(rows(f, free, "CONFIRMATION")[0].data_json)["basis"] == "FREE"
    for pol in (p, free):
        report = f.v1.reconcile(f.admin.token, pol)
        assert (
            report["cleared_pool_minor"]
            == report["spendable_pool_minor"]
            == report["observed_posted_debits_minor"]
            == 0
        )
        assert not report["issues"] and not report["monetary_flow_ready"]
    with f.sessions() as db:
        assert (
            db.query(FinancialOperation).count()
            == db.query(FinancialLedgerEntry).count()
            == 0
        )


def test_capacity_deadline_and_current_eligibility(v1, monkeypatch):
    f = v1
    p = create(f, price=0, capacity=1)
    register(f, p)
    f.v1.approve_eligibility(
        f.organiser.token,
        p,
        f.other.id,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    with pytest.raises(OperationConflict, match="capacity"):
        f.v1.register(f.other.token, p, idempotency_key=key())
    p2 = create(f)
    f.v1.approve_eligibility(
        f.organiser.token,
        p2,
        f.owner.id,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    monkeypatch.setattr(
        "app.services.tournament_v1.utc_now", lambda: f.deadline + timedelta(seconds=1)
    )
    with pytest.raises(OperationDenied, match="closed"):
        f.v1.register(f.owner.token, p2, idempotency_key=key())
    # Existing consent is replayed, not re-created after the deadline.
    assert (
        f.v1.register(f.owner.token, p, idempotency_key=key())
        == rows(f, p, "REGISTRATION")[0].id
    )


def test_concurrent_registration_retries_one_fee_obligation(v1):
    f = v1
    p = create(f)
    f.v1.approve_eligibility(
        f.organiser.token,
        p,
        f.owner.id,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    k = key()
    run = lambda: f.v1.register(f.owner.token, p, idempotency_key=k)
    result = _ordered_race(
        f.engine, run, run, update_marker="insert into tournament_registrations"
    )
    assert isinstance(result["first"], str) and result["first"] == result["second"]
    assert len(rows(f, p, "REGISTRATION")) == len(rows(f, p, "FEE_OBLIGATION")) == 1


def test_rollback_registration_request_and_fee_are_atomic(v1):
    f = v1
    p = create(f)
    f.v1.approve_eligibility(
        f.organiser.token,
        p,
        f.owner.id,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    k = key()

    def fail(connection, cursor, statement, parameters, context, many):
        if statement.lower().startswith("insert into tournament_v1_requests"):
            raise RuntimeError("Injected request failure")

    event.listen(f.engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Injected"):
            f.v1.register(f.owner.token, p, idempotency_key=k)
    finally:
        event.remove(f.engine, "before_cursor_execute", fail)
    assert not rows(f, p, "REGISTRATION") and not rows(f, p, "FEE_OBLIGATION")
    with f.sessions() as db:
        assert db.query(TournamentRegistration).count() == 0
    assert f.v1.register(f.owner.token, p, idempotency_key=k)


def test_fee_provenance_does_not_clear_pool_or_confirm_registration(v1):
    f = v1
    p = create(f)
    reg, ref, op = fee_reference(f, p)
    fee = rows(f, p, "FEE_OBLIGATION")[0]
    assert (
        f.v1.review_posted_fee_reference(
            f.checker.token, p, fee.id, op.id, idempotency_key=key()
        )
        == ref
    )
    with pytest.raises(OperationDenied):
        f.v1.review_posted_fee_reference(
            f.admin.token, p, fee.id, op.id, idempotency_key=key()
        )
    assert not rows(f, p, "CONFIRMATION")
    report = f.v1.reconcile(f.admin.token, p)
    assert (
        report["observed_posted_debits_minor"] == 100
        and report["cleared_pool_minor"] == report["spendable_pool_minor"] == 0
    )
    assert not report["issues"]
    f.v1.review_sponsorship(
        f.admin.token, p, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    assert rows(f, p, "SPONSOR_REVIEW")[0].amount_minor is None
    assert f.v1.reconcile(f.admin.token, p)["cleared_pool_minor"] == 0
    with pytest.raises(TournamentPolicyRequired):
        f.v1.monetary_action(f.admin.token, p)
    assert (
        f.wallets.reconcile()[0].consistent
        and f.service.reconcile(f.admin.token).consistent
    )


def test_partial_refund_reviews_principal_caps_ownership_and_concurrency(v1):
    f = v1
    p = create(f)
    _, ref, _ = fee_reference(f, p)
    with pytest.raises(OperationDenied):
        f.v1.request_refund_review(
            f.other.token, p, ref, amount_minor=1, idempotency_key=key()
        )
    k = key()
    first = f.v1.request_refund_review(
        f.owner.token, p, ref, amount_minor=30, idempotency_key=k
    )
    assert (
        f.v1.request_refund_review(
            f.owner.token, p, ref, amount_minor=30, idempotency_key=k
        )
        == first
    )
    with pytest.raises(OperationConflict):
        f.v1.request_refund_review(
            f.owner.token, p, ref, amount_minor=31, idempotency_key=k
        )
    run = lambda: f.v1.request_refund_review(
        f.owner.token, p, ref, amount_minor=50, idempotency_key=key()
    )
    race = _ordered_race(
        f.engine, run, run, update_marker="insert into tournament_v1_records"
    )
    assert isinstance(race["first"], str) and isinstance(
        race["second"], OperationConflict
    )
    assert sum(r.amount_minor for r in rows(f, p, "REFUND_REVIEW")) == 80
    with pytest.raises(OperationConflict):
        f.v1.request_refund_review(
            f.owner.token, p, ref, amount_minor=21, idempotency_key=key()
        )
    assert f.v1.reconcile(f.admin.token, p)["refunded_minor"] == 0
    cancel = f.v1.cancel_before_start(
        f.organiser.token, p, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    assert (
        cancel
        and json.loads(rows(f, p, "CANCELLATION")[0].data_json)["recommendation"]
        == "FULL_REMAINING_PRINCIPAL"
    )


def test_results_independent_approval_and_immutable_nonpostable_schedule(
    v1, monkeypatch
):
    f = v1
    p, rev, mids = finished(f, monkeypatch, 3)
    with pytest.raises(OperationDenied):
        f.v1.payout_schedule_preview(
            f.organiser.token,
            p,
            rev,
            hypothetical_distributable_minor=101,
            idempotency_key=key(),
        )
    # Administrators who proposed results cannot approve their own revision.
    with f.sessions() as db:
        user = db.get(User, f.organiser.id)
        user.role = "administrator"
        db.commit()
    with pytest.raises(OperationDenied):
        f.v1.approve_results(f.organiser.token, p, rev, idempotency_key=key())
    with pytest.raises(OperationDenied):
        f.v1.approve_results(f.checker.token, p, rev, idempotency_key=key())
    f.v1.approve_results(f.admin.token, p, rev, idempotency_key=key())
    schedule = f.v1.payout_schedule_preview(
        f.organiser.token,
        p,
        rev,
        hypothetical_distributable_minor=101,
        idempotency_key=key(),
    )
    assert (
        f.v1.payout_schedule_preview(
            f.organiser.token,
            p,
            rev,
            hypothetical_distributable_minor=101,
            idempotency_key=key(),
        )
        == schedule
    )
    with pytest.raises(OperationConflict):
        f.v1.payout_schedule_preview(
            f.organiser.token,
            p,
            rev,
            hypothetical_distributable_minor=102,
            idempotency_key=key(),
        )
    row = rows(f, p, "PAYOUT_SCHEDULE")[0]
    data = json.loads(row.data_json)
    assert row.amount_minor is row.operation_id is row.receipt_id is None
    assert data["postable"] is False and [
        s["amount_minor"] for s in data["shares"]
    ] == [61, 30, 10]
    assert not f.v1.reconcile(f.admin.token, p)["issues"]
    with pytest.raises(OperationDenied):
        f.v1.submit_result(
            f.organiser.token,
            p,
            mids[-1],
            2,
            1,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    f.v1.submit_result(
        f.organiser.token,
        p,
        mids[-1],
        2,
        1,
        evidence_digest=EVIDENCE,
        correction_digest="b" * 64,
        idempotency_key=key(),
    )
    assert "results_revision_stale" in f.v1.reconcile(f.admin.token, p)["issues"]
    with pytest.raises(OperationConflict):
        f.v1.payout_schedule_preview(
            f.organiser.token,
            p,
            rev,
            hypothetical_distributable_minor=101,
            idempotency_key=key(),
        )
    new = f.v1.lock_results(
        f.organiser.token,
        p,
        [f.owner.pid, f.other.pid, f.checker.pid],
        final_match_id=mids[-1],
        evidence_digest="b" * 64,
        idempotency_key=key(),
    )
    assert new != rev and len(rows(f, p, "RESULTS_REVISION")) == 2
    assert rows(f, p, "PAYOUT_SCHEDULE")[0].id == schedule


def test_invalid_standings_ties_unfinished_and_tampering(v1, monkeypatch):
    f = v1
    p = create(f, price=0)
    register(f, p)
    register(f, p, f.other)
    mid = f.v1.create_match(
        f.organiser.token, p, f.owner.pid, f.other.pid, idempotency_key=key()
    )
    monkeypatch.setattr(
        "app.services.tournament_v1.utc_now", lambda: f.starts + timedelta(seconds=1)
    )
    with pytest.raises(ValueError):
        f.v1.submit_result(
            f.organiser.token,
            p,
            mid,
            1,
            1,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    with pytest.raises(OperationConflict):
        f.v1.lock_results(
            f.organiser.token,
            p,
            [f.owner.pid, f.other.pid],
            final_match_id=mid,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    f.v1.submit_result(
        f.organiser.token, p, mid, 2, 0, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    for winners in (
        [f.owner.pid, f.owner.pid],
        [f.other.pid, f.owner.pid],
        [f.owner.pid, f.admin.pid],
    ):
        with pytest.raises(ValueError):
            f.v1.lock_results(
                f.organiser.token,
                p,
                winners,
                final_match_id=mid,
                evidence_digest=EVIDENCE,
                idempotency_key=key(),
            )
    with f.sessions() as db:
        match = db.get(Match, mid)
        match.score_player1 = 1
        db.commit()
    with pytest.raises(OperationConflict):
        f.v1.lock_results(
            f.organiser.token,
            p,
            [f.owner.pid, f.other.pid],
            final_match_id=mid,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )


def test_single_winner_review_stays_nonpostable(v1, monkeypatch):
    f = v1
    p, rev, _ = finished(f, monkeypatch, 1)
    f.v1.approve_results(f.admin.token, p, rev, idempotency_key=key())
    f.v1.payout_schedule_preview(
        f.organiser.token,
        p,
        rev,
        hypothetical_distributable_minor=1,
        idempotency_key=key(),
    )
    assert (
        json.loads(rows(f, p, "PAYOUT_SCHEDULE")[0].data_json)["shares"][0][
            "amount_minor"
        ]
        == 1
    )


def test_legacy_mutation_paths_cannot_bypass_v1(v1):
    f = v1
    p = create(f)
    with f.sessions() as db:
        policy = db.get(TournamentV1Policy, p)
        with pytest.raises(HTTPException) as err:
            crud.register_player(db, policy.tournament_id, f.owner.pid)
        assert err.value.status_code == 403
        with pytest.raises(HTTPException):
            crud.complete_tournament(db, policy.tournament_id, [])
        with pytest.raises(HTTPException):
            crud.create_match(
                db,
                schemas.MatchCreate(
                    tournament_id=policy.tournament_id,
                    player1_id=f.owner.pid,
                    player2_id=f.other.pid,
                ),
            )
    with pytest.raises(HTTPException):
        f.v1.monetary_action(f.owner.token, p)


def test_missing_v1_triggers_fail_closed(v1):
    f = v1
    p = create(f)
    with f.engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER v1_record_scope")
    with pytest.raises(FinancialError, match="V1 integrity"):
        f.v1.reconcile(f.admin.token, p)


def test_database_scope_constraints_and_reconciliation_source_changes(v1):
    f = v1
    p = create(f, price=0)
    reg = register(f, p)
    with f.sessions() as db:
        row = db.get(TournamentV1Record, reg)
        legacy = db.get(TournamentRegistration, row.registration_id)
        legacy.contribution = 1
        db.commit()
        with pytest.raises(IntegrityError, match="immutable"):
            db.execute(
                text(
                    "UPDATE tournament_v1_records SET financially_effective=1 WHERE id=:id"
                ),
                {"id": reg},
            )
    assert "registration_source_changed" in f.v1.reconcile(f.admin.token, p)["issues"]
    with pytest.raises(OperationConflict):
        f.v1.register(f.owner.token, p, idempotency_key=p)
    with pytest.raises(FinancialError):
        f.service.request(
            f.owner.token,
            f.owner.wallet.id,
            kind="deposit",
            amount=Decimal("1"),
            currency="BWP",
            idempotency_key=reg,
        )


def test_v1_migration_and_copy_preserve_populated_policy_and_refuse_downgrade(
    v1, tmp_path
):
    from alembic import command
    from app.db_cli import migration_config
    from scripts.verify_migrations import verify_existing_copy

    f = v1
    p = create(f, price=0)
    register(f, p)
    # Fixture source is disposable and intentionally unversioned, not snooker.db.
    source = tmp_path / "operations.db"
    target = tmp_path / "v1-compatible-copy.db"
    verify_existing_copy(source, target)
    config = migration_config("sqlite:///" + str(target))
    with pytest.raises(RuntimeError, match="Populated V1 policy"):
        command.downgrade(config, "i20261120tfin")
    import sqlite3

    with sqlite3.connect(target) as db:
        assert db.execute("SELECT id FROM tournament_v1_policies").fetchone() == (p,)
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "j20261120tv1",
        )


def test_two_winner_schedule_and_scope_rejections(v1, monkeypatch):
    f = v1
    p, rev, _ = finished(f, monkeypatch, 2)
    f.v1.approve_results(f.admin.token, p, rev, idempotency_key=key())
    f.v1.payout_schedule_preview(
        f.organiser.token,
        p,
        rev,
        hypothetical_distributable_minor=100,
        idempotency_key=key(),
    )
    assert [
        s["amount_minor"]
        for s in json.loads(rows(f, p, "PAYOUT_SCHEDULE")[0].data_json)["shares"]
    ] == [67, 33]
    with pytest.raises(HTTPException):
        f.v1.reconcile(f.owner.token, p)
    with pytest.raises(HTTPException):
        f.v1.approve_results(f.other.token, p, rev, idempotency_key=key())


def test_four_player_third_place_requires_decisive_semifinal_losers(v1, monkeypatch):
    f = v1
    p = create(f, price=0)
    actors = [f.owner, f.other, f.checker, f.admin]
    for actor in actors:
        register(f, p, actor)
    matches = [
        f.v1.create_match(f.organiser.token, p, a.pid, b.pid, idempotency_key=key())
        for a, b in (
            (f.owner, f.checker),
            (f.other, f.admin),
            (f.owner, f.other),
            (f.checker, f.admin),
        )
    ]
    monkeypatch.setattr(
        "app.services.tournament_v1.utc_now", lambda: f.starts + timedelta(seconds=1)
    )
    for mid in matches:
        f.v1.submit_result(
            f.organiser.token,
            p,
            mid,
            2,
            0,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    winners = [f.owner.pid, f.other.pid, f.checker.pid]
    with pytest.raises(ValueError):
        f.v1.lock_results(
            f.organiser.token,
            p,
            winners,
            final_match_id=matches[2],
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    rev = f.v1.lock_results(
        f.organiser.token,
        p,
        winners,
        final_match_id=matches[2],
        third_match_id=matches[3],
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    assert (
        len(json.loads(rows(f, p, "RESULTS_REVISION")[0].data_json)["matches"]) == 4
        and rev
    )


def test_bye_is_not_an_unplayed_decisive_match(v1, monkeypatch):
    f = v1
    p = create(f, price=0)
    register(f, p)
    register(f, p, f.other)
    bye = f.v1.create_match(
        f.organiser.token, p, f.owner.pid, None, idempotency_key=key()
    )
    final = f.v1.create_match(
        f.organiser.token, p, f.owner.pid, f.other.pid, idempotency_key=key()
    )
    monkeypatch.setattr(
        "app.services.tournament_v1.utc_now", lambda: f.starts + timedelta(seconds=1)
    )
    with pytest.raises(ValueError):
        f.v1.submit_result(
            f.organiser.token,
            p,
            bye,
            2,
            0,
            evidence_digest=EVIDENCE,
            idempotency_key=key(),
        )
    f.v1.submit_result(
        f.organiser.token, p, bye, 0, 0, evidence_digest=EVIDENCE, idempotency_key=key()
    )
    f.v1.submit_result(
        f.organiser.token,
        p,
        final,
        2,
        0,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )
    assert f.v1.lock_results(
        f.organiser.token,
        p,
        [f.owner.pid, f.other.pid],
        final_match_id=final,
        evidence_digest=EVIDENCE,
        idempotency_key=key(),
    )


def test_new_tournament_financial_http_paths_remain_denied(v1):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    f = v1
    p = create(f)
    with f.sessions() as db:
        tid = db.get(TournamentV1Policy, p).tournament_id
    previous = app.dependency_overrides.get(get_db)

    def database():
        with f.sessions() as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            for actor in (f.owner, f.admin):
                headers = {"Authorization": "Bearer " + actor.token}
                for route in ("deposit", "withdraw"):
                    response = client.post(
                        f"/players/{f.owner.pid}/{route}",
                        json={"amount": 1},
                        headers=headers,
                    )
                    assert response.status_code == 403
                    assert (
                        response.json()["detail"]["code"]
                        == "FINANCIAL_OPERATIONS_DISABLED"
                    )
                assert (
                    client.post(
                        f"/tournaments/{tid}/register",
                        json={"player_id": f.owner.pid},
                        headers=headers,
                    ).status_code
                    == 403
                )
            assert (
                client.post(
                    f"/tournaments/{tid}/complete",
                    json=[],
                    headers={"Authorization": "Bearer " + f.admin.token},
                ).status_code
                == 403
            )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous
    with f.sessions() as db:
        assert (
            db.query(FinancialOperation).count()
            == db.query(FinancialLedgerEntry).count()
            == 0
        )
