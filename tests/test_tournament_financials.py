"""Policy-neutral review identities; no fee/refund/prize/token rule is assumed."""

from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import event, select, update, delete
from sqlalchemy.exc import IntegrityError

from tests.test_financial_operations import ops, password_hash
from tests.test_financial_wallets import _ordered_race
from app import crud, schemas
from app.models import (
    Tournament,
    TournamentOrganiser,
    TournamentRegistration,
    TournamentResult,
    TournamentStatus,
    Match,
    TournamentFinancialIntent,
    TournamentFinancialRequest,
    FinancialOperation,
    FinancialLedgerEntry,
)
from app.services.financial_operations import OperationConflict, OperationDenied
from app.services.financial_wallets import FinancialError
from app.services.tournament_financials import (
    TournamentFinancialService,
    TournamentPolicyRequired,
)


@pytest.fixture
def reviews(ops):
    with ops.sessions() as db:
        tournament = Tournament(name="Review only", entry_fee=25)
        unassigned = Tournament(name="Unassigned", entry_fee=0)
        db.add_all([tournament, unassigned])
        db.flush()
        first = TournamentRegistration(
            tournament_id=tournament.id, player_id=ops.owner.pid
        )
        second = TournamentRegistration(
            tournament_id=tournament.id, player_id=ops.other.pid
        )
        other = TournamentRegistration(
            tournament_id=unassigned.id, player_id=ops.owner.pid
        )
        db.add_all([first, second, other])
        db.flush()
        result = TournamentResult(
            tournament_id=tournament.id, player_id=ops.owner.pid, position=1
        )
        runner = TournamentResult(
            tournament_id=tournament.id, player_id=ops.other.pid, position=2
        )
        db.add_all(
            [
                result,
                runner,
                TournamentOrganiser(
                    tournament_id=tournament.id, user_id=ops.organiser.id
                ),
            ]
        )
        db.commit()
        ops.tid, ops.reg, ops.other_reg, ops.unassigned_reg = (
            tournament.id,
            first.id,
            second.id,
            other.id,
        )
        ops.result, ops.runner = result.id, runner.id
    ops.reviews = TournamentFinancialService(ops.engine)
    return ops


def fee(f, key=None, actor=None, registration=None):
    return f.reviews.record_fee_review(
        (actor or f.admin).token,
        registration or f.reg,
        idempotency_key=key or str(uuid4()),
    )


def totals(f):
    with f.sessions() as db:
        return (
            db.query(TournamentFinancialIntent).count(),
            db.query(TournamentFinancialRequest).count(),
            db.query(FinancialOperation).count(),
            db.query(FinancialLedgerEntry).count(),
        )


@pytest.mark.parametrize("kind", ["FEE", "REFUND", "PAYOUT"])
def test_intents_have_durable_identity_but_no_unapproved_money(reviews, kind):
    f = reviews
    method = {
        "FEE": f.reviews.record_fee_review,
        "REFUND": f.reviews.record_refund_review,
        "PAYOUT": f.reviews.record_payout_review,
    }[kind]
    context = f.result if kind == "PAYOUT" else f.reg
    key = str(uuid4())
    first = method(f.admin.token, context, idempotency_key=key)
    assert method(f.admin.token, context, idempotency_key=key) == first
    assert method(f.admin.token, context, idempotency_key=str(uuid4())).id == first.id
    assert first.kind == kind and first.status == "POLICY_REQUIRED"
    assert (
        first.amount_minor
        is first.currency
        is first.operation_id
        is first.receipt_id
        is None
    )
    report = f.reviews.reconcile(f.admin.token, f.tid)
    assert (
        report.consistent and report.policy_required and not report.monetary_flow_ready
    )
    assert report.prize_pool is report.token_allocation is None
    assert totals(f) == (1, 2, 0, 0)


def test_semantic_deduplication_keeps_every_distinct_request_key_bound(reviews):
    f = reviews
    first_key, second_key = str(uuid4()), str(uuid4())
    first = fee(f, first_key)
    assert fee(f, second_key).id == first.id
    with pytest.raises(OperationConflict):
        fee(f, second_key, registration=f.other_reg)
    with pytest.raises(OperationConflict):
        f.reviews.record_refund_review(f.admin.token, f.reg, idempotency_key=first_key)
    assert totals(f) == (1, 2, 0, 0)


@pytest.mark.parametrize("actor_name", ["owner", "other", "checker"])
def test_review_authority_is_current_tournament_assignment_not_wallet_ownership(
    reviews, actor_name
):
    f = reviews
    actor = getattr(f, actor_name)
    if actor_name == "checker":
        # A current administrator is allowed; organisers are checked separately below.
        assert fee(f, actor=actor).status == "POLICY_REQUIRED"
    else:
        with pytest.raises(HTTPException) as error:
            fee(f, actor=actor)
        assert error.value.status_code == 403


def test_assigned_organiser_can_record_but_not_reconcile_or_bypass_policy(reviews):
    f = reviews
    intent = fee(f, actor=f.organiser)
    assert f.reviews.get(f.organiser.token, intent.id) == intent
    with pytest.raises(HTTPException):
        fee(f, actor=f.organiser, registration=f.unassigned_reg)
    with pytest.raises(OperationDenied):
        f.reviews.reconcile(f.organiser.token, f.tid)
    with pytest.raises(TournamentPolicyRequired):
        f.reviews.post_intent(f.organiser.token, intent.id)
    assert totals(f) == (1, 1, 0, 0)


def test_revoked_assignment_and_invalid_token_are_not_authority(reviews):
    f = reviews
    intent = fee(f, actor=f.organiser)
    with f.sessions() as db:
        db.execute(
            delete(TournamentOrganiser).where(
                TournamentOrganiser.user_id == f.organiser.id
            )
        )
        db.commit()
    with pytest.raises(HTTPException):
        f.reviews.get(f.organiser.token, intent.id)
    with pytest.raises(HTTPException) as error:
        f.reviews.record_fee_review("invalid", f.reg, idempotency_key=str(uuid4()))
    assert error.value.status_code == 401


def test_admin_cannot_create_or_post_money_or_guess_token_policy(reviews):
    f = reviews
    intent = fee(f)
    for method in (f.reviews.create_operation, f.reviews.post_intent):
        with pytest.raises(TournamentPolicyRequired):
            method(f.admin.token, intent.id)
    with pytest.raises(TournamentPolicyRequired):
        f.reviews.allocate_tokens(f.admin.token, f.tid)
    with pytest.raises(TypeError):
        f.reviews.record_fee_review(
            f.admin.token,
            f.reg,
            idempotency_key=str(uuid4()),
            amount=Decimal("25"),
            currency="BWP",
        )
    assert totals(f) == (1, 1, 0, 0)


def test_blocked_identifiers_cannot_bypass_via_operations_or_wallet_primitive(reviews):
    f = reviews
    key = str(uuid4())
    intent = fee(f, key)
    for reserved in (intent.id, key):
        with pytest.raises(FinancialError, match="Tournament policy"):
            f.wallets.post(
                f.owner.wallet.id,
                kind="deposit",
                amount=Decimal("1"),
                currency="BWP",
                idempotency_key=reserved,
            )
        with pytest.raises(FinancialError, match="Tournament policy"):
            f.service.request(
                f.admin.token,
                f.owner.wallet.id,
                kind="fee",
                amount=Decimal("1"),
                currency="BWP",
                idempotency_key=reserved,
            )
    assert totals(f) == (1, 1, 0, 0)


def test_existing_operation_key_is_not_adopted_by_tournament_review(reviews):
    f = reviews
    key = str(uuid4())
    f.service.request(
        f.owner.token,
        f.owner.wallet.id,
        kind="deposit",
        amount=Decimal("1"),
        currency="BWP",
        idempotency_key=key,
    )
    with pytest.raises(OperationConflict):
        fee(f, key)
    assert totals(f) == (0, 0, 1, 0)


def test_source_price_flags_or_status_changes_are_diagnosed_not_converted(reviews):
    f = reviews
    intent = fee(f)
    with f.sessions() as db:
        registration = db.get(TournamentRegistration, f.reg)
        registration.paid = True
        registration.waived = True
        registration.contribution = 17
        tournament = db.get(Tournament, f.tid)
        tournament.entry_fee = 50
        tournament.status = TournamentStatus.CANCELLED
        db.commit()
    assert fee(f).id == intent.id
    report = f.reviews.reconcile(f.admin.token, f.tid)
    assert report.issues == ("review_source_changed",) and report.prize_pool is None
    with f.sessions() as db:
        assert db.get(Tournament, f.tid).entry_fee == 50
        assert db.get(TournamentRegistration, f.reg).contribution == 17
    assert totals(f) == (1, 2, 0, 0)


def test_duplicate_ranked_players_and_unregistered_winners_are_not_payable_proof(
    reviews,
):
    f = reviews
    with f.sessions() as db:
        db.get(TournamentResult, f.runner).player_id = f.owner.pid
        db.add(
            TournamentResult(tournament_id=f.tid, player_id=f.organiser.pid, position=4)
        )
        db.commit()
    f.reviews.record_payout_review(
        f.admin.token, f.result, idempotency_key=str(uuid4())
    )
    report = f.reviews.reconcile(f.admin.token, f.tid)
    assert {
        "duplicate_ranked_player",
        "unregistered_ranked_player",
        "rank_positions_need_review",
    } <= set(report.issues)
    assert not report.monetary_flow_ready and totals(f)[2:] == (0, 0)


def test_invalid_match_winners_scores_and_unfinished_completion_are_diagnostics(
    reviews,
):
    f = reviews
    with f.sessions() as db:
        db.get(Tournament, f.tid).status = TournamentStatus.COMPLETED
        db.add_all(
            [
                Match(
                    tournament_id=f.tid,
                    player1_id=f.owner.pid,
                    player2_id=f.other.pid,
                    winner_id=f.organiser.pid,
                    score_player1=-1,
                ),
                Match(
                    tournament_id=f.tid, player1_id=f.owner.pid, player2_id=f.other.pid
                ),
            ]
        )
        db.commit()
    report = f.reviews.reconcile(f.admin.token, f.tid)
    assert {
        "winner_not_match_participant",
        "negative_match_score",
        "completed_with_unfinished_match",
    } <= set(report.issues)
    assert totals(f) == (0, 0, 0, 0)


def test_completed_without_rankings_is_not_a_payout_instruction(reviews):
    f = reviews
    with f.sessions() as db:
        db.execute(
            delete(TournamentResult).where(TournamentResult.tournament_id == f.tid)
        )
        db.get(Tournament, f.tid).status = TournamentStatus.COMPLETED
        db.commit()
    assert (
        "completed_without_standings"
        in f.reviews.reconcile(f.admin.token, f.tid).issues
    )
    assert totals(f) == (0, 0, 0, 0)


def test_completion_and_review_retries_do_not_duplicate_financial_operations(reviews):
    f = reviews
    with f.sessions() as db:
        tournament = Tournament(name="Free completion regression", entry_fee=0)
        db.add(tournament)
        db.flush()
        db.add(
            TournamentRegistration(tournament_id=tournament.id, player_id=f.owner.pid)
        )
        db.commit()
        tid = tournament.id
        result = crud.complete_tournament(
            db, tid, [schemas.WinnerCreate(player_id=f.owner.pid, position=1)]
        )[0]
        rid = result.id
        with pytest.raises(HTTPException) as error:
            crud.complete_tournament(
                db, tid, [schemas.WinnerCreate(player_id=f.owner.pid, position=1)]
            )
        assert error.value.status_code == 400
    first = f.reviews.record_payout_review(
        f.admin.token, rid, idempotency_key=str(uuid4())
    )
    assert (
        f.reviews.record_payout_review(
            f.admin.token, rid, idempotency_key=str(uuid4())
        ).id
        == first.id
    )
    assert totals(f) == (1, 2, 0, 0)


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_review_requests_have_one_identity_and_no_money(reviews, same_key):
    f = reviews
    key = str(uuid4())
    result = _ordered_race(
        f.engine,
        lambda: fee(f, key),
        lambda: fee(f, key if same_key else str(uuid4())),
        update_marker="insert into tournament_financial_intents",
    )
    assert (
        not isinstance(result["first"], Exception)
        and result["first"].id == result["second"].id
    )
    assert totals(f) == (1, 1 if same_key else 2, 0, 0)


def test_concurrent_conflicting_request_key_is_not_reused(reviews):
    f = reviews
    key = str(uuid4())
    result = _ordered_race(
        f.engine,
        lambda: fee(f, key),
        lambda: fee(f, key, registration=f.other_reg),
        update_marker="insert into tournament_financial_intents",
    )
    assert not isinstance(result["first"], Exception) and isinstance(
        result["second"], OperationConflict
    )
    assert totals(f) == (1, 1, 0, 0)


def test_request_insert_failure_rolls_back_new_intent_and_key(reviews):
    f = reviews
    key = str(uuid4())

    def failure(connection, cursor, statement, parameters, context, many):
        if statement.lower().startswith("insert into tournament_financial_requests"):
            raise RuntimeError("Injected review history failure")

    event.listen(f.engine, "before_cursor_execute", failure)
    try:
        with pytest.raises(RuntimeError):
            fee(f, key)
    finally:
        event.remove(f.engine, "before_cursor_execute", failure)
    assert totals(f) == (0, 0, 0, 0)
    assert fee(f, key).status == "POLICY_REQUIRED" and totals(f) == (1, 1, 0, 0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("currency", "BWP"),
        ("amount_minor", 1),
        ("status", "POSTED"),
        ("operation_id", str(uuid4())),
    ],
)
def test_database_prevents_approval_or_monetary_binding_even_for_admin(
    reviews, field, value
):
    f = reviews
    intent = fee(f)
    with f.sessions() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                update(TournamentFinancialIntent)
                .where(TournamentFinancialIntent.id == intent.id)
                .values({field: value})
            )
            db.commit()
        db.rollback()
    assert totals(f) == (1, 1, 0, 0)


def test_missing_review_protections_fail_closed(reviews):
    f = reviews
    with f.engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER tournament_intent_no_update")
    with pytest.raises(FinancialError, match="triggers missing or changed"):
        fee(f)
    assert totals(f) == (0, 0, 0, 0)
