"""Test-only evidence adapters; none of these simulate settlement in application code."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import event, select, update, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, make_engine
from app.models import (
    User,
    Player,
    FinancialOperation,
    FinancialOperationAudit,
    FinancialWallet,
    FinancialLedgerEntry,
)
from app.money import InvalidMoney
from app.payment_verification import VerifiedEvidence, VerificationUnavailable
from app.security import create_session, hash_password
from app.services.financial_wallets import (
    FinancialWalletService,
    FinancialError,
    InsufficientFunds,
)
from app.services.financial_operations import (
    FinancialOperationService,
    OperationConflict,
    OperationDenied,
    InvalidTransition,
    VerificationRejected,
)
from app.time import utc_now
from tests.test_financial_wallets import _ordered_race


class TestEvidenceAdapter:
    __test__ = False
    provider = "test-only-provider"

    def __init__(self):
        self.transform = lambda evidence: evidence
        self.callback = None

    def verify(self, request, reference):
        if self.callback:
            self.callback()
        evidence = VerifiedEvidence(
            request.operation_id,
            request.wallet_id,
            request.kind,
            request.amount_minor,
            request.currency,
            self.provider,
            hashlib.sha256(reference.encode()).hexdigest(),
            hashlib.sha256(request.operation_id.encode()).hexdigest(),
            utc_now(),
        )
        return self.transform(evidence)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password("Operation-test-only-password!123")


@pytest.fixture
def ops(tmp_path, password_hash):
    engine = make_engine(f"sqlite:///{tmp_path / 'operations.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    accounts = {}
    with sessions() as db:
        for name, role in (
            ("owner", "player"),
            ("other", "player"),
            ("organiser", "organiser"),
            ("admin", "administrator"),
            ("checker", "administrator"),
        ):
            player = Player(name=name)
            db.add(player)
            db.flush()
            user = User(
                username=name,
                role=role,
                password_hash=password_hash,
                player_id=player.id,
            )
            db.add(user)
            db.flush()
            token, _ = create_session(db, user)
            accounts[name] = SimpleNamespace(id=user.id, pid=player.id, token=token)
        db.commit()
    wallets = FinancialWalletService(engine)
    for account in accounts.values():
        account.wallet = wallets.open_wallet(account.pid, currency="BWP")
    adapter = TestEvidenceAdapter()
    service = FinancialOperationService(engine, verifier=adapter)
    yield SimpleNamespace(
        engine=engine,
        sessions=sessions,
        wallets=wallets,
        adapter=adapter,
        service=service,
        **accounts,
    )
    engine.dispose()


def request(f, *, actor=None, wallet=None, amount="1.00", kind="deposit", key=None):
    return f.service.request(
        (actor or f.owner).token,
        (wallet or f.owner.wallet).id,
        amount=Decimal(amount),
        currency="BWP",
        kind=kind,
        idempotency_key=key or str(uuid4()),
    )


def verify(f, op, *, actor=None, reference=None):
    return f.service.verify(
        (actor or f.admin).token,
        op.id,
        reference=reference or "test-reference:" + op.id,
    )


def posted(f, *, amount="100", kind="deposit", actor=None):
    op = request(f, actor=actor, amount=amount, kind=kind)
    verify(f, op, actor=f.checker if actor else f.admin)
    return f.service.post((f.checker if actor else f.admin).token, op.id)


def counts(f):
    with f.sessions() as db:
        return (
            db.query(FinancialOperation).count(),
            db.query(FinancialLedgerEntry).count(),
            db.query(FinancialOperationAudit).count(),
        )


def test_complete_workflow_is_atomic_authenticated_and_exact(ops):
    op = request(ops, amount="0.30")
    assert op.owner_id == ops.owner.id and op.status == "PENDING"
    assert op.wallet_id == ops.owner.wallet.id and op.amount == Decimal("0.30")
    verified = verify(ops, op)
    assert verified.status == "VERIFIED" and verified.receipt_id is None
    assert all(r.entry_count == 0 for r in ops.wallets.reconcile())
    receipt = ops.service.post(ops.admin.token, op.id)
    assert receipt.amount == receipt.balance_after == Decimal("0.30")
    assert ops.service.get(ops.owner.token, op.id).status == "POSTED"
    assert ops.service.post(ops.admin.token, op.id) == receipt
    assert ops.service.reconcile(ops.admin.token).consistent
    assert counts(ops) == (1, 1, 3)


def test_default_verifier_fails_closed_and_never_claims_confirmation(ops):
    service = FinancialOperationService(ops.engine)
    op = request(ops)
    with pytest.raises(VerificationUnavailable):
        service.verify(ops.admin.token, op.id, reference="opaque-provider-reference")
    with pytest.raises(InvalidTransition):
        service.post(ops.admin.token, op.id)
    assert service.get(ops.owner.token, op.id).status == "PENDING"
    assert counts(ops) == (1, 0, 1)


@pytest.mark.parametrize("name", ["owner", "organiser", "admin"])
def test_deposit_withdrawal_requests_cannot_target_another_owner(ops, name):
    with pytest.raises(OperationDenied):
        request(ops, actor=getattr(ops, name), wallet=ops.other.wallet)
    assert counts(ops) == (0, 0, 0)


def test_cross_owner_read_and_cancel_denied_even_with_known_id(ops):
    op = request(ops)
    for action in (ops.service.get, ops.service.cancel):
        with pytest.raises(OperationDenied):
            action(ops.other.token, op.id)
    with pytest.raises(OperationDenied):
        ops.service.get(ops.other.token, str(uuid4()))
    assert ops.service.get(ops.admin.token, op.id).owner_id == ops.owner.id


@pytest.mark.parametrize("kind", ["fee", "prize"])
def test_staff_types_need_admin_and_independent_checker(ops, kind):
    for actor in (ops.owner, ops.organiser):
        with pytest.raises(OperationDenied):
            request(ops, actor=actor, kind=kind)
    if kind == "fee":
        ops.wallets.post(
            ops.owner.wallet.id,
            kind="deposit",
            amount=Decimal("2"),
            currency="BWP",
            idempotency_key=str(uuid4()),
        )
    op = request(ops, actor=ops.admin, kind=kind)
    with pytest.raises(OperationDenied):
        verify(ops, op, actor=ops.admin)
    verify(ops, op, actor=ops.checker)
    receipt = ops.service.post(ops.checker.token, op.id)
    assert receipt.kind == kind and ops.service.reconcile(ops.admin.token).consistent


def test_administrator_cannot_self_verify_or_self_post(ops):
    op = request(ops, actor=ops.admin, wallet=ops.admin.wallet)
    with pytest.raises(OperationDenied):
        verify(ops, op, actor=ops.admin)
    verify(ops, op, actor=ops.checker)
    with pytest.raises(OperationDenied):
        ops.service.post(ops.admin.token, op.id)
    assert ops.service.post(ops.checker.token, op.id).amount == Decimal("1.00")


@pytest.mark.parametrize("name", ["owner", "other", "organiser"])
def test_nonadmins_have_no_verification_posting_rejection_or_reconciliation_privileges(
    ops, name
):
    op = request(ops)
    actor = getattr(ops, name)
    with pytest.raises(OperationDenied):
        verify(ops, op, actor=actor)
    with pytest.raises(OperationDenied):
        ops.service.post(actor.token, op.id)
    with pytest.raises(OperationDenied):
        ops.service.reject(actor.token, op.id)
    with pytest.raises(OperationDenied):
        ops.service.reconcile(actor.token)


def test_owner_and_role_inputs_are_not_accepted(ops):
    with pytest.raises(TypeError):
        ops.service.request(
            ops.owner.token,
            ops.owner.wallet.id,
            amount=Decimal("1"),
            currency="BWP",
            kind="deposit",
            idempotency_key=str(uuid4()),
            owner_id=ops.other.id,
        )
    assert counts(ops) == (0, 0, 0)


@pytest.mark.parametrize(
    "amount",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("0.001"),
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("90000000000000.01"),
        1.0,
        True,
        1,
    ],
)
def test_invalid_operation_amounts_never_create_intents(ops, amount):
    with pytest.raises(InvalidMoney):
        ops.service.request(
            ops.owner.token,
            ops.owner.wallet.id,
            amount=amount,
            currency="BWP",
            kind="deposit",
            idempotency_key=str(uuid4()),
        )
    assert counts(ops) == (0, 0, 0)


@pytest.mark.parametrize("currency", ["USD", "bwp", "", None])
def test_unsupported_currency_never_creates_operation(ops, currency):
    with pytest.raises(InvalidMoney):
        ops.service.request(
            ops.owner.token,
            ops.owner.wallet.id,
            amount=Decimal("1"),
            currency=currency,
            kind="deposit",
            idempotency_key=str(uuid4()),
        )


def test_request_keys_are_unique_and_payload_conflicts_are_not_replays(ops):
    key = str(uuid4())
    first = request(ops, key=key)
    assert request(ops, key=key) == first
    with pytest.raises(OperationConflict):
        request(ops, amount="2", key=key)
    with pytest.raises(OperationConflict):
        request(ops, actor=ops.other, wallet=ops.other.wallet, key=key)
    assert counts(ops) == (1, 0, 1)


def test_existing_standalone_ledger_key_cannot_be_adopted(ops):
    key = str(uuid4())
    ops.wallets.post(
        ops.owner.wallet.id,
        kind="deposit",
        amount=Decimal("1"),
        currency="BWP",
        idempotency_key=key,
    )
    with pytest.raises(OperationConflict):
        request(ops, key=key)
    report = ops.service.reconcile(ops.admin.token)
    assert report.consistent and report.unmanaged_ledger_entries == 1


@pytest.mark.parametrize("phase", ["PENDING", "VERIFIED", "POSTED"])
def test_public_wallet_primitive_cannot_bypass_operation_workflow(ops, phase):
    op = request(ops)
    if phase != "PENDING":
        verify(ops, op)
    if phase == "POSTED":
        ops.service.post(ops.admin.token, op.id)
    for key in (op.id, op.idempotency_key):
        with pytest.raises(FinancialError, match="Operation-managed"):
            ops.wallets.post(
                op.wallet_id,
                kind=op.kind,
                amount=op.amount,
                currency="BWP",
                idempotency_key=key,
            )
    assert counts(ops)[1] == (1 if phase == "POSTED" else 0)


@pytest.mark.parametrize(
    "change",
    [
        "operation_id",
        "wallet_id",
        "kind",
        "amount_minor",
        "currency",
        "provider",
        "digest",
        "time",
        "dict",
    ],
)
def test_unbound_stale_or_client_shaped_evidence_is_rejected(ops, change):
    op = request(ops)

    def bad(e):
        if change == "dict":
            return {"verified": True, "settled": True}
        values = {
            "operation_id": str(uuid4()),
            "wallet_id": str(uuid4()),
            "kind": "prize",
            "amount_minor": 999,
            "currency": "USD",
            "provider": "untrusted",
            "payload_digest": "not-a-hash",
            "checked_at": utc_now() - timedelta(days=1),
        }
        field = {"digest": "payload_digest", "time": "checked_at"}.get(change, change)
        return replace(e, **{field: values[field]})

    ops.adapter.transform = bad
    with pytest.raises(VerificationRejected):
        verify(ops, op)
    assert ops.service.get(ops.owner.token, op.id).status == "PENDING" and counts(
        ops
    ) == (1, 0, 1)


def test_client_verification_flags_are_not_a_method_contract(ops):
    op = request(ops)
    with pytest.raises(TypeError):
        ops.service.verify(
            ops.admin.token, op.id, reference="ref", verified=True, settled=True
        )
    assert counts(ops) == (1, 0, 1)


def test_provider_event_cannot_be_reused_even_through_an_alias(ops):
    first, second = request(ops), request(ops)
    ops.adapter.transform = lambda e: replace(e, event_digest="a" * 64)
    verify(ops, first, reference="alias-one")
    with pytest.raises(OperationConflict):
        verify(ops, second, reference="alias-two")
    assert ops.service.get(ops.owner.token, second.id).status == "PENDING"
    assert counts(ops) == (2, 0, 3)


def test_verification_retries_are_idempotent_and_cannot_replace_evidence(ops):
    op = request(ops)
    result = verify(ops, op)
    assert verify(ops, op) == result
    with pytest.raises(OperationConflict):
        verify(ops, op, reference="replacement")
    assert counts(ops) == (1, 0, 2)


def test_only_digests_and_safe_reason_codes_are_persisted(ops):
    op = request(ops)
    secret = "opaque-reference-with-sensitive-test-content"
    verify(ops, op, reference=secret)
    with ops.sessions() as db:
        stored = db.get(FinancialOperation, op.id)
        assert stored.reference_digest == hashlib.sha256(secret.encode()).hexdigest()
        assert (
            stored.provider_event_digest != secret
            and len(stored.provider_payload_digest) == 64
        )
        audit = db.scalars(select(FinancialOperationAudit)).all()
        assert [(e.event, e.reason_code) for e in audit] == [
            ("created", "requested"),
            ("verified", "evidence_verified"),
        ]
        assert secret not in str([e.__dict__ for e in audit])


def test_provider_exception_is_sanitised_without_state_change(ops):
    op = request(ops)

    def failure():
        raise RuntimeError("client_secret=DO_NOT_PERSIST")

    ops.adapter.callback = failure
    with pytest.raises(VerificationUnavailable) as error:
        verify(ops, op)
    assert "DO_NOT_PERSIST" not in str(error.value) and counts(ops) == (1, 0, 1)


@pytest.mark.parametrize("terminal", ["cancel", "reject"])
def test_terminal_states_do_not_reopen_and_exact_abort_retry_is_safe(ops, terminal):
    op = request(ops)
    actor = ops.owner if terminal == "cancel" else ops.admin
    method = getattr(ops.service, terminal)
    result = method(actor.token, op.id)
    assert method(actor.token, op.id) == result
    with pytest.raises(InvalidTransition):
        verify(ops, op)
    with pytest.raises(InvalidTransition):
        ops.service.post(ops.admin.token, op.id)
    assert counts(ops) == (1, 0, 2)


def test_verified_can_be_rejected_but_not_cancelled_and_posted_is_terminal(ops):
    first = request(ops)
    verify(ops, first)
    with pytest.raises(InvalidTransition):
        ops.service.cancel(ops.owner.token, first.id)
    assert ops.service.reject(ops.admin.token, first.id).status == "REJECTED"
    second = request(ops)
    verify(ops, second)
    ops.service.post(ops.admin.token, second.id)
    for method in (ops.service.reject, ops.service.cancel):
        with pytest.raises(InvalidTransition):
            method(ops.admin.token, second.id)
    assert ops.service.reconcile(ops.admin.token).consistent


@pytest.mark.parametrize("actor_name", ["owner", "admin"])
def test_deactivation_or_demotion_enforced_from_current_database(ops, actor_name):
    op = request(ops)
    with ops.sessions() as db:
        actor = db.get(User, getattr(ops, actor_name).id)
        if actor_name == "owner":
            actor.is_active = False
        else:
            actor.role = "player"
        db.commit()
    with pytest.raises(OperationDenied):
        verify(ops, op)
    assert counts(ops) == (1, 0, 1)


def test_invalid_expired_and_revoked_access_tokens_are_not_actors(ops):
    from app.models import AuthSession
    import jwt
    from app.auth_config import get_auth_config

    config = get_auth_config()
    claims = jwt.decode(
        ops.owner.token,
        config.secret,
        algorithms=["HS256"],
        issuer=config.issuer,
        audience=config.audience,
    )
    claims["exp"] = 1
    expired = jwt.encode(claims, config.secret, algorithm="HS256")
    for token in ("invalid", expired):
        with pytest.raises(HTTPException) as error:
            ops.service.request(
                token,
                ops.owner.wallet.id,
                amount=Decimal("1"),
                currency="BWP",
                kind="deposit",
                idempotency_key=str(uuid4()),
            )
        assert error.value.status_code == 401
    with ops.sessions() as db:
        db.query(AuthSession).filter_by(user_id=ops.owner.id).update(
            {"revoked_at": utc_now()}
        )
        db.commit()
    with pytest.raises(HTTPException):
        request(ops)
    assert counts(ops) == (0, 0, 0)


def test_verified_evidence_expiry_blocks_posting(ops, monkeypatch):
    import app.services.financial_operations as module

    op = request(ops)
    verify(ops, op)
    future = utc_now() + timedelta(minutes=16)
    monkeypatch.setattr(module, "utc_now", lambda: future)
    with pytest.raises(VerificationRejected):
        ops.service.post(ops.admin.token, op.id)
    assert ops.service.get(ops.owner.token, op.id).status == "VERIFIED" and counts(
        ops
    ) == (1, 0, 2)


def test_insufficient_funds_does_not_post_operation_and_retry_can_succeed(ops):
    debit = request(ops, amount="80", kind="withdrawal")
    verify(ops, debit)
    with pytest.raises(InsufficientFunds):
        ops.service.post(ops.admin.token, debit.id)
    assert ops.service.get(ops.owner.token, debit.id).status == "VERIFIED"
    posted(ops, amount="100")
    receipt = ops.service.post(ops.admin.token, debit.id)
    assert receipt.balance_after == Decimal("20.00") and counts(ops) == (2, 2, 6)
    assert ops.service.reconcile(ops.admin.token).consistent


@pytest.mark.parametrize("failure", ["state", "audit", "commit"])
def test_posting_failures_rollback_wallet_ledger_state_and_audit_together(ops, failure):
    op = request(ops)
    verify(ops, op)

    def fail_sql(connection, cursor, statement, parameters, context, many):
        sql = statement.lstrip().lower()
        if (failure == "state" and sql.startswith("update financial_operations")) or (
            failure == "audit"
            and sql.startswith("insert into financial_operation_audit")
        ):
            raise RuntimeError("Injected coordinated failure")

    def fail_commit(db):
        raise RuntimeError("Injected coordinated failure")

    target, name, hook = (
        (Session, "before_commit", fail_commit)
        if failure == "commit"
        else (ops.engine, "before_cursor_execute", fail_sql)
    )
    event.listen(target, name, hook)
    try:
        with pytest.raises(RuntimeError, match="coordinated failure"):
            ops.service.post(ops.admin.token, op.id)
    finally:
        event.remove(target, name, hook)
    assert ops.service.get(ops.owner.token, op.id).status == "VERIFIED" and counts(
        ops
    ) == (1, 0, 2)
    assert all(r.consistent and r.balance == 0 for r in ops.wallets.reconcile())
    assert ops.service.reconcile(ops.admin.token).consistent
    receipt = ops.service.post(ops.admin.token, op.id)
    assert ops.service.post(ops.admin.token, op.id) == receipt and counts(ops) == (
        1,
        1,
        3,
    )


def test_lost_response_after_commit_retries_original_receipt(ops, monkeypatch):
    op = request(ops)
    verify(ops, op)
    original = ops.service._transaction

    @contextmanager
    def lose_reply(*, write):
        with original(write=write) as db:
            yield db
        if write:
            raise RuntimeError("Simulated lost reply after commit")

    with monkeypatch.context() as patch:
        patch.setattr(ops.service, "_transaction", lose_reply)
        with pytest.raises(RuntimeError, match="lost reply"):
            ops.service.post(ops.admin.token, op.id)
    assert ops.service.get(ops.owner.token, op.id).status == "POSTED"
    receipt = ops.service.post(ops.admin.token, op.id)
    assert receipt.amount == Decimal("1.00") and counts(ops) == (1, 1, 3)


def test_cancellation_racing_verification_cannot_resurrect_operation(ops):
    op = request(ops)
    entered, release = Event(), Event()
    results = []

    def pause():
        entered.set()
        if not release.wait(15):
            raise RuntimeError("Test verifier wait expired")

    ops.adapter.callback = pause

    def worker():
        try:
            results.append(verify(ops, op))
        except Exception as error:
            results.append(error)

    thread = Thread(target=worker)
    try:
        thread.start()
        assert entered.wait(10)
        assert ops.service.cancel(ops.owner.token, op.id).status == "CANCELLED"
    finally:
        release.set()
        thread.join(15)
    assert not thread.is_alive() and isinstance(results[0], InvalidTransition)
    assert counts(ops) == (1, 0, 2)


def test_concurrent_posts_of_same_operation_create_one_receipt(ops):
    op = request(ops)
    verify(ops, op)
    result = _ordered_race(
        ops.engine,
        lambda: ops.service.post(ops.admin.token, op.id),
        lambda: ops.service.post(ops.admin.token, op.id),
    )
    assert result["first"] == result["second"] and not isinstance(
        result["first"], Exception
    )
    assert (
        counts(ops) == (1, 1, 3) and ops.service.reconcile(ops.admin.token).consistent
    )


def test_concurrent_operations_cannot_spend_same_balance_twice(ops):
    posted(ops, amount="100")
    first, second = request(ops, amount="80", kind="withdrawal"), request(
        ops, amount="80", kind="withdrawal"
    )
    verify(ops, first)
    verify(ops, second)
    result = _ordered_race(
        ops.engine,
        lambda: ops.service.post(ops.admin.token, first.id),
        lambda: ops.service.post(ops.admin.token, second.id),
    )
    assert not isinstance(result["first"], Exception) and isinstance(
        result["second"], InsufficientFunds
    )
    assert ops.service.get(ops.owner.token, first.id).status == "POSTED"
    assert ops.service.get(ops.owner.token, second.id).status == "VERIFIED"
    assert any(r.balance == Decimal("20.00") for r in ops.wallets.reconcile())
    assert ops.service.reconcile(ops.admin.token).consistent and counts(ops) == (
        3,
        2,
        8,
    )


@pytest.mark.parametrize("conflict", [False, True])
def test_concurrent_requests_share_one_intent_or_conflict(ops, conflict):
    key = str(uuid4())
    result = _ordered_race(
        ops.engine,
        lambda: request(ops, key=key),
        lambda: request(ops, amount="2" if conflict else "1", key=key),
        update_marker="insert into financial_operations",
    )
    if conflict:
        assert isinstance(result["second"], OperationConflict)
    else:
        assert result["first"] == result["second"]
    assert counts(ops) == (1, 0, 1)


def test_concurrent_verification_is_one_transition(ops):
    op = request(ops)
    result = _ordered_race(
        ops.engine,
        lambda: verify(ops, op),
        lambda: verify(ops, op),
        update_marker="update financial_operations",
    )
    assert result["first"] == result["second"] and not isinstance(
        result["first"], Exception
    )
    assert counts(ops) == (1, 0, 2)


@pytest.mark.parametrize("post_first", [True, False])
def test_post_and_reject_race_has_only_one_terminal_outcome(ops, post_first):
    op = request(ops)
    verify(ops, op)
    post = lambda: ops.service.post(ops.admin.token, op.id)
    reject = lambda: ops.service.reject(ops.admin.token, op.id)
    result = _ordered_race(
        ops.engine,
        post if post_first else reject,
        reject if post_first else post,
        update_marker=(
            "update financial_wallets" if post_first else "update financial_operations"
        ),
    )
    assert not isinstance(result["first"], Exception) and isinstance(
        result["second"], InvalidTransition
    )
    assert ops.service.get(ops.owner.token, op.id).status == (
        "POSTED" if post_first else "REJECTED"
    )
    assert counts(ops) == (1, 1 if post_first else 0, 3)
    assert ops.service.reconcile(ops.admin.token).consistent


def test_operation_and_audit_database_guards_are_not_optional(ops):
    op = request(ops)
    for statement in (
        update(FinancialOperation)
        .where(FinancialOperation.id == op.id)
        .values(amount_minor=999),
        update(FinancialOperation)
        .where(FinancialOperation.id == op.id)
        .values(status="POSTED"),
        delete(FinancialOperation).where(FinancialOperation.id == op.id),
        update(FinancialOperationAudit).values(reason_code="posted"),
        delete(FinancialOperationAudit),
    ):
        with ops.sessions() as db:
            with pytest.raises(IntegrityError):
                db.execute(statement)
                db.commit()
            db.rollback()
    assert counts(ops) == (1, 0, 1)


def test_operation_reconciliation_detects_missing_audit_without_repair(ops):
    op = request(ops)
    verify(ops, op)
    ops.service.post(ops.admin.token, op.id)
    with ops.engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER operation_audit_no_delete")
        db.execute(
            delete(FinancialOperationAudit).where(
                FinancialOperationAudit.event == "posted"
            )
        )
        from app.operation_schema import OPERATION_TRIGGERS

        db.exec_driver_sql(OPERATION_TRIGGERS["operation_audit_no_delete"])
    report = ops.service.reconcile(ops.admin.token)
    assert not report.consistent and report.operations[0].issues == (
        "operation_audit_history_mismatch",
    )
    assert counts(ops) == (1, 1, 2)


def test_missing_operation_protections_fail_closed(ops):
    with ops.engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER operation_update_guard")
    with pytest.raises(FinancialError, match="triggers missing or changed"):
        request(ops)
    assert counts(ops) == (0, 0, 0)


def test_signed_role_claim_cannot_grant_financial_reviewer_permissions(ops):
    import jwt
    from app.auth_config import get_auth_config

    op = request(ops)
    config = get_auth_config()
    claims = jwt.decode(
        ops.owner.token,
        config.secret,
        algorithms=["HS256"],
        issuer=config.issuer,
        audience=config.audience,
    )
    claims["role"] = "administrator"
    forged = jwt.encode(claims, config.secret, algorithm="HS256")
    with pytest.raises(OperationDenied):
        ops.service.verify(forged, op.id, reference="client-claimed-role")
    assert counts(ops) == (1, 0, 1)


@pytest.mark.parametrize(
    "change", ["owner_inactive", "checker_demoted", "owner_relinked"]
)
def test_permissions_and_ownership_rechecked_after_provider_boundary(ops, change):
    op = request(ops)

    def concurrent_change():
        with ops.sessions() as db:
            if change == "owner_inactive":
                db.get(User, ops.owner.id).is_active = False
            elif change == "checker_demoted":
                db.get(User, ops.admin.id).role = "player"
            else:
                player = Player(name="Different ownership after verification started")
                db.add(player)
                db.flush()
                db.get(User, ops.owner.id).player_id = player.id
            db.commit()

    ops.adapter.callback = concurrent_change
    with pytest.raises(OperationDenied):
        verify(ops, op)
    assert counts(ops) == (1, 0, 1)


def test_reconciliation_detects_wrong_receipt_link_and_refuses_replay(ops):
    op = request(ops)
    verify(ops, op)
    ops.service.post(ops.admin.token, op.id)
    other = ops.wallets.post(
        ops.owner.wallet.id,
        kind="deposit",
        amount=Decimal("2"),
        currency="BWP",
        idempotency_key=str(uuid4()),
    )
    from app.operation_schema import OPERATION_TRIGGERS

    with ops.engine.begin() as db:
        db.exec_driver_sql("DROP TRIGGER operation_update_guard")
        db.execute(
            update(FinancialOperation)
            .where(FinancialOperation.id == op.id)
            .values(receipt_id=other.id)
        )
        db.exec_driver_sql(OPERATION_TRIGGERS["operation_update_guard"])
    report = ops.service.reconcile(ops.admin.token)
    assert not report.consistent and report.operations[0].issues == (
        "operation_receipt_binding_mismatch",
    )
    with pytest.raises(OperationConflict):
        ops.service.post(ops.admin.token, op.id)
    assert counts(ops) == (1, 2, 3)


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount_minor", 0),
        ("amount_minor", -1),
        ("amount_minor", 0.5),
        ("amount_minor", 9_000_000_000_000_001),
        ("currency", "USD"),
        ("status", "POSTED"),
        ("idempotency_key", "bad"),
        ("owner_id", 999999),
        ("verified_at", utc_now()),
    ],
)
def test_operation_database_checks_reject_invalid_direct_intents(ops, field, value):
    values = dict(
        id=str(uuid4()),
        idempotency_key=str(uuid4()),
        owner_id=ops.owner.id,
        requested_by_id=ops.owner.id,
        last_actor_id=ops.owner.id,
        wallet_id=ops.owner.wallet.id,
        amount_minor=100,
        currency="BWP",
        kind="deposit",
        status="PENDING",
    )
    values[field] = value
    with ops.sessions() as db:
        db.add(FinancialOperation(**values))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert counts(ops) == (0, 0, 0)
