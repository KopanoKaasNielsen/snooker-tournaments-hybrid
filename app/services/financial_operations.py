"""Authenticated internal operation coordination. No financial HTTP/provider activation."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import hashlib
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    FinancialOperation,
    FinancialOperationAudit,
    FinancialWallet,
    FinancialLedgerEntry,
    User,
)
from app.money import from_minor_units, to_minor_units
from app.operation_schema import operation_triggers_match
from app.payment_verification import (
    PaymentEvidenceVerifier,
    UnavailablePaymentVerifier,
    VerificationRequest,
    VerifiedEvidence,
    VerificationUnavailable,
)
from app.security import token_identity
from app.services.financial_wallets import (
    FinancialError,
    FinancialWalletService,
    Receipt,
    _key,
    _receipt,
)
from app.time import utc_now


class OperationDenied(FinancialError):
    pass


class OperationConflict(FinancialError):
    pass


class InvalidTransition(FinancialError):
    pass


class VerificationRejected(FinancialError):
    pass


@dataclass(frozen=True)
class OperationView:
    id: str
    idempotency_key: str
    owner_id: int
    requested_by_id: int
    wallet_id: str
    amount: Decimal
    currency: str
    kind: str
    status: str
    provider: str | None
    receipt_id: str | None


@dataclass(frozen=True)
class OperationReconciliation:
    operation_id: str
    status: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ReconciliationBatch:
    operations: tuple[OperationReconciliation, ...]
    unmanaged_ledger_entries: int

    @property
    def consistent(self) -> bool:
        return all(not item.issues for item in self.operations)


def _view(op: FinancialOperation) -> OperationView:
    return OperationView(
        op.id,
        op.idempotency_key,
        op.owner_id,
        op.requested_by_id,
        op.wallet_id,
        from_minor_units(op.amount_minor, currency=op.currency),
        op.currency,
        op.kind,
        op.status,
        op.provider,
        op.receipt_id,
    )


def _binding(op: FinancialOperation) -> VerificationRequest:
    return VerificationRequest(
        op.id, op.wallet_id, op.kind, op.amount_minor, op.currency
    )


def _reference(reference: str) -> str:
    if (
        not isinstance(reference, str)
        or not 1 <= len(reference) <= 256
        or any(ord(c) < 32 or ord(c) > 126 for c in reference)
    ):
        raise VerificationRejected("A bounded opaque evidence reference is required")
    return hashlib.sha256(reference.encode()).hexdigest()


def _audit(db, op, actor, event: str, previous: str | None, reason: str):
    db.add(
        FinancialOperationAudit(
            id=str(uuid4()),
            operation_id=op.id,
            actor_id=actor.id,
            actor_role=actor.role,
            event=event,
            reason_code=reason,
            from_status=previous,
            to_status=op.status,
        )
    )
    db.flush()


class FinancialOperationService:
    def __init__(self, engine, *, verifier: PaymentEvidenceVerifier | None = None):
        self.wallets = FinancialWalletService(engine)
        self.verifier = (
            verifier if verifier is not None else UnavailablePaymentVerifier()
        )

    @contextmanager
    def _transaction(self, *, write: bool):
        with self.wallets._transaction(write=write) as db:
            if not operation_triggers_match(db.connection()):
                raise FinancialError(
                    "Operation integrity triggers missing or changed; verify migrations"
                )
            yield db

    @staticmethod
    def _actor(db, access_token: str) -> User:
        return token_identity(db, access_token)[0]

    @staticmethod
    def _operation(db, actor: User, operation_id: str) -> FinancialOperation:
        op = db.get(FinancialOperation, operation_id)
        if op is None or (actor.role != "administrator" and actor.id != op.owner_id):
            raise OperationDenied("Operation unavailable or not permitted")
        if actor.role != "administrator":
            wallet = db.get(FinancialWallet, op.wallet_id)
            if wallet is None or wallet.player_id != actor.player_id:
                raise OperationDenied("Operation unavailable or not permitted")
        return op

    @staticmethod
    def _owner_active(db, op):
        owner, wallet = db.get(User, op.owner_id), db.get(FinancialWallet, op.wallet_id)
        if (
            not owner
            or not owner.is_active
            or not wallet
            or wallet.player_id != owner.player_id
        ):
            raise OperationDenied("Current active wallet ownership is required")

    @staticmethod
    def _checker(actor, op):
        if actor.role != "administrator" or actor.id in (
            op.owner_id,
            op.requested_by_id,
        ):
            raise OperationDenied(
                "Independent administrator required; no owner/requester bypass"
            )

    def request(
        self,
        access_token: str,
        wallet_id: str,
        *,
        amount: Decimal,
        currency: str,
        kind: str,
        idempotency_key: str,
    ) -> OperationView:
        with self._transaction(write=True) as db:
            actor = self._actor(db, access_token)
            units = to_minor_units(amount, currency=currency)
            _key(idempotency_key)
            from app.tournament_financial_schema import key_reserved

            if key_reserved(db.connection(), idempotency_key):
                raise FinancialError(
                    "Tournament policy required before financial operation creation"
                )
            if kind not in ("deposit", "withdrawal", "fee", "prize"):
                raise FinancialError("Unsupported operation type")
            wallet = db.get(FinancialWallet, wallet_id)
            owner = (
                db.scalar(select(User).where(User.player_id == wallet.player_id))
                if wallet
                else None
            )
            if (
                not owner
                or not owner.is_active
                or (kind in ("deposit", "withdrawal") and owner.id != actor.id)
                or (
                    kind in ("fee", "prize")
                    and (actor.role != "administrator" or actor.id == owner.id)
                )
            ):
                raise OperationDenied("Wallet unavailable or requester not permitted")
            previous = db.scalar(
                select(FinancialOperation).where(
                    FinancialOperation.idempotency_key == idempotency_key
                )
            )
            if previous is not None:
                if (
                    previous.wallet_id,
                    previous.owner_id,
                    previous.requested_by_id,
                    previous.kind,
                    previous.amount_minor,
                    previous.currency,
                ) != (wallet_id, owner.id, actor.id, kind, units, currency):
                    raise OperationConflict("Request key belongs to different intent")
                return _view(previous)
            if db.scalar(
                select(FinancialLedgerEntry.id).where(
                    FinancialLedgerEntry.idempotency_key == idempotency_key
                )
            ) or db.get(FinancialOperation, idempotency_key):
                raise OperationConflict("Request key is already reserved")
            identifier = str(uuid4())
            if key_reserved(db.connection(), identifier):
                raise OperationConflict(
                    "Operation identifier is reserved; retry same request key"
                )
            if db.scalar(
                select(FinancialLedgerEntry.id).where(
                    FinancialLedgerEntry.idempotency_key == identifier
                )
            ) or db.scalar(
                select(FinancialOperation.id).where(
                    FinancialOperation.idempotency_key == identifier
                )
            ):
                raise OperationConflict(
                    "Operation identifier conflict; retry same request key"
                )
            op = FinancialOperation(
                id=identifier,
                idempotency_key=idempotency_key,
                owner_id=owner.id,
                requested_by_id=actor.id,
                last_actor_id=actor.id,
                wallet_id=wallet_id,
                amount_minor=units,
                currency=currency,
                kind=kind,
                status="PENDING",
            )
            db.add(op)
            db.flush()
            _audit(db, op, actor, "created", None, "requested")
            result = _view(op)
        return result

    def get(self, access_token: str, operation_id: str) -> OperationView:
        with self._transaction(write=False) as db:
            return _view(
                self._operation(db, self._actor(db, access_token), operation_id)
            )

    def verify(
        self, access_token: str, operation_id: str, *, reference: str
    ) -> OperationView:
        digest = _reference(reference)
        with self._transaction(write=False) as db:
            actor = self._actor(db, access_token)
            op = self._operation(db, actor, operation_id)
            self._checker(actor, op)
            self._owner_active(db, op)
            if op.status in ("VERIFIED", "POSTED"):
                if op.reference_digest != digest:
                    raise OperationConflict("Verified reference cannot be replaced")
                return _view(op)
            if op.status != "PENDING":
                raise InvalidTransition("Only pending operations can be verified")
            request, created_at = _binding(op), op.created_at
        # No writer lock is held while a future approved adapter performs verification.
        try:
            evidence = self.verifier.verify(request, reference)
        except Exception:
            raise VerificationUnavailable(
                "Evidence verifier unavailable or refused request"
            ) from None
        self._validate_evidence(request, created_at, evidence)
        try:
            with self._transaction(write=True) as db:
                actor = self._actor(db, access_token)
                op = self._operation(db, actor, operation_id)
                self._checker(actor, op)
                self._owner_active(db, op)
                if op.status in ("VERIFIED", "POSTED"):
                    if (
                        op.reference_digest,
                        op.provider,
                        op.provider_event_digest,
                        op.provider_payload_digest,
                    ) != (
                        digest,
                        evidence.provider,
                        evidence.event_digest,
                        evidence.payload_digest,
                    ):
                        raise OperationConflict("Different evidence already recorded")
                    return _view(op)
                if op.status != "PENDING" or _binding(op) != request:
                    raise InvalidTransition(
                        "Operation changed while verification was in progress"
                    )
                op.status = "VERIFIED"
                op.provider, op.provider_event_digest = (
                    evidence.provider,
                    evidence.event_digest,
                )
                op.provider_payload_digest, op.reference_digest = (
                    evidence.payload_digest,
                    digest,
                )
                op.verified_at, op.verified_by_id = evidence.checked_at, actor.id
                op.updated_at, op.last_actor_id = utc_now(), actor.id
                db.flush()
                _audit(db, op, actor, "verified", "PENDING", "evidence_verified")
                result = _view(op)
            return result
        except IntegrityError:
            raise OperationConflict(
                "Evidence event is unavailable or already bound to an operation"
            ) from None

    def _validate_evidence(self, request, created_at, evidence):
        now = utc_now()
        if (
            not isinstance(evidence, VerifiedEvidence)
            or type(evidence.amount_minor) is not int
        ):
            raise VerificationRejected("Trusted verifier returned invalid evidence")
        if (
            VerificationRequest(
                evidence.operation_id,
                evidence.wallet_id,
                evidence.kind,
                evidence.amount_minor,
                evidence.currency,
            )
            != request
        ):
            raise VerificationRejected(
                "Evidence does not match the immutable operation"
            )
        if (
            not isinstance(evidence.provider, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", evidence.provider)
            or evidence.provider != self.verifier.provider
        ):
            raise VerificationRejected("Evidence provider mismatch")
        if any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in (evidence.event_digest, evidence.payload_digest)
        ):
            raise VerificationRejected("Invalid digest-only evidence")
        from datetime import datetime

        if (
            not isinstance(evidence.checked_at, datetime)
            or evidence.checked_at.tzinfo is not None
            or not created_at <= evidence.checked_at <= now + timedelta(seconds=5)
            or now - evidence.checked_at > timedelta(minutes=5)
        ):
            raise VerificationRejected("Evidence verification time is invalid or stale")

    @staticmethod
    def _matching_entry(db, op):
        entry = db.get(FinancialLedgerEntry, op.receipt_id) if op.receipt_id else None
        if not entry or (
            entry.idempotency_key,
            entry.wallet_id,
            entry.currency,
            entry.kind,
            entry.amount_minor,
        ) != (op.id, op.wallet_id, op.currency, op.kind, op.amount_minor):
            raise OperationConflict("Operation and ledger receipt do not match")
        return entry

    def post(self, access_token: str, operation_id: str) -> Receipt:
        with self._transaction(write=True) as db:
            actor = self._actor(db, access_token)
            op = self._operation(db, actor, operation_id)
            self._checker(actor, op)
            self._owner_active(db, op)
            if op.status == "POSTED":
                return _receipt(self._matching_entry(db, op))
            if op.status != "VERIFIED":
                raise InvalidTransition("Only verified operations can post")
            verifier = db.get(User, op.verified_by_id)
            if (
                not verifier
                or not verifier.is_active
                or verifier.role != "administrator"
                or utc_now() - op.verified_at > timedelta(minutes=15)
            ):
                raise VerificationRejected(
                    "Current independent verification is required"
                )
            if db.scalar(
                select(FinancialLedgerEntry.id).where(
                    FinancialLedgerEntry.idempotency_key == op.id
                )
            ):
                raise OperationConflict("An uncoordinated receipt cannot be adopted")
            receipt = self.wallets._post_in_session(
                db,
                op.wallet_id,
                kind=op.kind,
                amount=from_minor_units(op.amount_minor, currency=op.currency),
                currency=op.currency,
                idempotency_key=op.id,
                _operation_id=op.id,
            )
            op.status, op.receipt_id = "POSTED", receipt.id
            op.posted_at, op.posted_by_id = utc_now(), actor.id
            op.updated_at, op.last_actor_id = op.posted_at, actor.id
            db.flush()
            _audit(db, op, actor, "posted", "VERIFIED", "posted")
        return receipt

    def reject(self, access_token: str, operation_id: str) -> OperationView:
        return self._abort(access_token, operation_id, reject=True)

    def cancel(self, access_token: str, operation_id: str) -> OperationView:
        return self._abort(access_token, operation_id, reject=False)

    def _abort(self, token, operation_id, *, reject):
        target = "REJECTED" if reject else "CANCELLED"
        with self._transaction(write=True) as db:
            actor = self._actor(db, token)
            op = self._operation(db, actor, operation_id)
            if reject and actor.role != "administrator":
                raise OperationDenied("Rejection requires administrator")
            if op.status == target:
                return _view(op)
            if op.status not in (("PENDING", "VERIFIED") if reject else ("PENDING",)):
                raise InvalidTransition(
                    "Operation cannot enter requested terminal state"
                )
            previous = op.status
            op.status, op.updated_at, op.last_actor_id = target, utc_now(), actor.id
            if reject:
                op.rejected_at = op.updated_at
            else:
                op.cancelled_at = op.updated_at
            db.flush()
            _audit(
                db,
                op,
                actor,
                "rejected" if reject else "cancelled",
                previous,
                (
                    "policy_rejected"
                    if reject
                    else (
                        "owner_cancelled"
                        if actor.id == op.owner_id
                        else "admin_cancelled"
                    )
                ),
            )
            result = _view(op)
        return result

    def reconcile(self, access_token: str) -> ReconciliationBatch:
        with self._transaction(write=False) as db:
            actor = self._actor(db, access_token)
            if actor.role != "administrator":
                raise OperationDenied("Financial reconciliation requires administrator")
            reports = []
            operations = db.scalars(
                select(FinancialOperation).order_by(FinancialOperation.id)
            ).all()
            for op in operations:
                issues = []
                entry = db.scalar(
                    select(FinancialLedgerEntry).where(
                        FinancialLedgerEntry.idempotency_key == op.id
                    )
                )
                if op.status == "POSTED":
                    try:
                        matched = self._matching_entry(db, op)
                        if entry is None or matched.id != entry.id:
                            issues.append("operation_receipt_key_mismatch")
                    except OperationConflict:
                        issues.append("operation_receipt_binding_mismatch")
                elif entry is not None or op.receipt_id is not None:
                    issues.append("nonposted_operation_has_ledger")
                expected = {"created": (None, "PENDING", op.requested_by_id)}
                if op.verified_at is not None:
                    expected["verified"] = ("PENDING", "VERIFIED", op.verified_by_id)
                if op.status in ("POSTED", "REJECTED", "CANCELLED"):
                    event = op.status.lower()
                    before = "VERIFIED" if op.verified_at is not None else "PENDING"
                    expected[event] = (before, op.status, op.last_actor_id)
                audit = db.scalars(
                    select(FinancialOperationAudit).where(
                        FinancialOperationAudit.operation_id == op.id
                    )
                ).all()
                if len(audit) != len(expected) or any(
                    e.event not in expected
                    or (e.from_status, e.to_status, e.actor_id) != expected.get(e.event)
                    for e in audit
                ):
                    issues.append("operation_audit_history_mismatch")
                reports.append(OperationReconciliation(op.id, op.status, tuple(issues)))
            unmanaged = len(
                db.scalars(
                    select(FinancialLedgerEntry.id).where(
                        ~FinancialLedgerEntry.idempotency_key.in_(
                            select(FinancialOperation.id)
                        )
                    )
                ).all()
            )
            return ReconciliationBatch(tuple(reports), unmanaged)
