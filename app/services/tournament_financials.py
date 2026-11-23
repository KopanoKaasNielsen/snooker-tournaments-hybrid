"""Policy-blocked tournament review identities; never calculate, create or post money."""

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select, or_

from app.models import (
    Tournament,
    TournamentRegistration,
    TournamentResult,
    Match,
    TournamentFinancialIntent,
    TournamentFinancialRequest,
    FinancialOperation,
    FinancialLedgerEntry,
)
from app.security import tournament_permission
from app.services.financial_operations import (
    FinancialOperationService,
    OperationDenied,
    OperationConflict,
)
from app.services.financial_wallets import FinancialError, _key
from app.tournament_financial_schema import triggers_match, key_reserved


class TournamentPolicyRequired(FinancialError):
    pass


@dataclass(frozen=True)
class ReviewIntent:
    id: str
    kind: str
    tournament_id: int
    player_id: int
    registration_id: int | None
    result_id: int | None
    status: str
    source_changed: bool
    amount_minor: None = None
    currency: None = None
    operation_id: None = None
    receipt_id: None = None


@dataclass(frozen=True)
class TournamentReconciliation:
    tournament_id: int
    intent_count: int
    request_count: int
    issues: tuple[str, ...]
    policy_required: bool = True
    monetary_flow_ready: bool = False
    prize_pool: None = None
    token_allocation: None = None

    @property
    def consistent(self) -> bool:
        """Metadata consistency only, never payment or eligibility approval."""
        return not self.issues


class TournamentFinancialService:
    def __init__(self, engine):
        self.operations = FinancialOperationService(engine)

    @contextmanager
    def _transaction(self, *, write):
        with self.operations._transaction(write=write) as db:
            if not triggers_match(db.connection()):
                raise FinancialError(
                    "Tournament review integrity triggers missing or changed"
                )
            yield db

    def _authority(self, db, token, tournament_id):
        actor = self.operations._actor(db, token)
        tournament_permission(db, actor, tournament_id)
        tournament = db.get(Tournament, tournament_id)
        if tournament is None:
            raise OperationDenied("Tournament review unavailable")
        return actor, tournament

    @staticmethod
    def _scope(db, kind, scope_id):
        model = TournamentResult if kind == "PAYOUT" else TournamentRegistration
        row = db.get(model, scope_id)
        if row is None:
            raise OperationDenied("Review context unavailable")
        return row

    @staticmethod
    def _digest(tournament, row):
        fields = {
            "id": row.id,
            "tournament_id": row.tournament_id,
            "player_id": row.player_id,
            "entry_fee_unknown_units": str(tournament.entry_fee),
            "tournament_status": tournament.status.value,
        }
        if isinstance(row, TournamentRegistration):
            fields.update(
                paid=row.paid,
                waived=row.waived,
                contribution_unknown_units=str(row.contribution),
            )
        else:
            fields.update(position=row.position)
        return hashlib.sha256(
            json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def _view(self, db, intent):
        row = self._scope(
            db,
            intent.kind,
            intent.result_id if intent.kind == "PAYOUT" else intent.registration_id,
        )
        tournament = db.get(Tournament, intent.tournament_id)
        return ReviewIntent(
            intent.id,
            intent.kind,
            intent.tournament_id,
            intent.player_id,
            intent.registration_id,
            intent.result_id,
            intent.status,
            self._digest(tournament, row) != intent.scope_digest,
        )

    @staticmethod
    def _money_key_exists(db, key):
        return (
            db.scalar(
                select(FinancialOperation.id).where(
                    or_(
                        FinancialOperation.id == key,
                        FinancialOperation.idempotency_key == key,
                    )
                )
            )
            is not None
            or db.scalar(
                select(FinancialLedgerEntry.id).where(
                    FinancialLedgerEntry.idempotency_key == key
                )
            )
            is not None
        )

    def record_fee_review(self, token, registration_id, *, idempotency_key):
        return self._record(token, "FEE", registration_id, idempotency_key)

    def record_refund_review(self, token, registration_id, *, idempotency_key):
        return self._record(token, "REFUND", registration_id, idempotency_key)

    def record_payout_review(self, token, result_id, *, idempotency_key):
        return self._record(token, "PAYOUT", result_id, idempotency_key)

    def _record(self, token, kind, scope_id, request_key):
        with self._transaction(write=True) as db:
            # Authenticate before looking up a caller-selected context.
            self.operations._actor(db, token)
            row = self._scope(db, kind, scope_id)
            actor, tournament = self._authority(db, token, row.tournament_id)
            _key(request_key)
            previous = db.get(TournamentFinancialRequest, request_key)
            if previous is not None:
                intent = db.get(TournamentFinancialIntent, previous.intent_id)
                if (
                    previous.requested_by_id,
                    intent.kind,
                    intent.registration_id,
                    intent.result_id,
                    intent.tournament_id,
                    intent.player_id,
                ) != (
                    actor.id,
                    kind,
                    None if kind == "PAYOUT" else row.id,
                    row.id if kind == "PAYOUT" else None,
                    row.tournament_id,
                    row.player_id,
                ):
                    raise OperationConflict(
                        "Review request key belongs to a different context"
                    )
                return self._view(db, intent)
            if key_reserved(db.connection(), request_key) or self._money_key_exists(
                db, request_key
            ):
                raise OperationConflict(
                    "Request key is reserved by another financial identity"
                )
            context = (
                TournamentFinancialIntent.result_id
                if kind == "PAYOUT"
                else TournamentFinancialIntent.registration_id
            )
            intent = db.scalar(
                select(TournamentFinancialIntent).where(
                    TournamentFinancialIntent.kind == kind, context == scope_id
                )
            )
            if intent is None:
                identifier = str(uuid4())
                if key_reserved(db.connection(), identifier) or self._money_key_exists(
                    db, identifier
                ):
                    raise OperationConflict(
                        "Review identifier conflict; retry same request key"
                    )
                intent = TournamentFinancialIntent(
                    id=identifier,
                    kind=kind,
                    tournament_id=row.tournament_id,
                    player_id=row.player_id,
                    registration_id=None if kind == "PAYOUT" else row.id,
                    result_id=row.id if kind == "PAYOUT" else None,
                    requested_by_id=actor.id,
                    scope_digest=self._digest(tournament, row),
                    status="POLICY_REQUIRED",
                )
                db.add(intent)
                db.flush()
            elif (intent.tournament_id, intent.player_id) != (
                row.tournament_id,
                row.player_id,
            ):
                raise OperationConflict(
                    "Stored review scope changed; explicit review required"
                )
            db.add(
                TournamentFinancialRequest(
                    idempotency_key=request_key,
                    intent_id=intent.id,
                    requested_by_id=actor.id,
                    actor_role=actor.role,
                )
            )
            db.flush()
            result = self._view(db, intent)
        return result

    def get(self, token, intent_id):
        with self._transaction(write=False) as db:
            self.operations._actor(db, token)
            intent = db.get(TournamentFinancialIntent, intent_id)
            if intent is None:
                raise OperationDenied("Review unavailable")
            self._authority(db, token, intent.tournament_id)
            return self._view(db, intent)

    def create_operation(self, token, intent_id):
        self.get(token, intent_id)
        raise TournamentPolicyRequired(
            "Fee/refund/payout policy is unapproved; no financial operation can be created"
        )

    def post_intent(self, token, intent_id):
        return self.create_operation(token, intent_id)

    def allocate_tokens(self, token, tournament_id):
        with self._transaction(write=False) as db:
            self._authority(db, token, tournament_id)
        raise TournamentPolicyRequired(
            "Token meaning, funding and pool deduction policy are unapproved"
        )

    def reconcile(self, token, tournament_id):
        with self._transaction(write=False) as db:
            actor, tournament = self._authority(db, token, tournament_id)
            if actor.role != "administrator":
                raise OperationDenied("Financial reconciliation requires administrator")
            intents = db.scalars(
                select(TournamentFinancialIntent).where(
                    TournamentFinancialIntent.tournament_id == tournament_id
                )
            ).all()
            issues, request_count = [], 0
            for intent in intents:
                view = self._view(db, intent)
                if view.source_changed:
                    issues.append("review_source_changed")
                requests = db.scalars(
                    select(TournamentFinancialRequest).where(
                        TournamentFinancialRequest.intent_id == intent.id
                    )
                ).all()
                request_count += len(requests)
                if not requests:
                    issues.append("review_request_history_missing")
                if any(
                    self._money_key_exists(db, key)
                    for key in [intent.id] + [r.idempotency_key for r in requests]
                ):
                    issues.append("policy_blocked_identifier_has_financial_activity")
                if any(
                    value is not None
                    for value in (
                        intent.operation_id,
                        intent.receipt_id,
                        intent.amount_minor,
                        intent.currency,
                    )
                ):
                    issues.append("unapproved_monetary_binding")
            registrations = db.scalars(
                select(TournamentRegistration).where(
                    TournamentRegistration.tournament_id == tournament_id
                )
            ).all()
            registered = {r.player_id for r in registrations}
            results = db.scalars(
                select(TournamentResult).where(
                    TournamentResult.tournament_id == tournament_id
                )
            ).all()
            players, positions = [r.player_id for r in results], [
                r.position for r in results
            ]
            if len(players) != len(set(players)):
                issues.append("duplicate_ranked_player")
            if len(positions) != len(set(positions)) or any(
                p not in range(1, 5) for p in positions
            ):
                issues.append("invalid_rank_positions")
            if results and sorted(positions) != list(range(1, len(positions) + 1)):
                issues.append("rank_positions_need_review")
            if not set(players).issubset(registered):
                issues.append("unregistered_ranked_player")
            if tournament.status.value == "COMPLETED" and not results:
                issues.append("completed_without_standings")
            matches = db.scalars(
                select(Match).where(Match.tournament_id == tournament_id)
            ).all()
            for match in matches:
                if match.winner_id is not None and match.winner_id not in (
                    match.player1_id,
                    match.player2_id,
                ):
                    issues.append("winner_not_match_participant")
                if any(
                    score is not None and score < 0
                    for score in (match.score_player1, match.score_player2)
                ):
                    issues.append("negative_match_score")
                if tournament.status.value == "COMPLETED" and match.winner_id is None:
                    issues.append("completed_with_unfinished_match")
            return TournamentReconciliation(
                tournament_id, len(intents), request_count, tuple(dict.fromkeys(issues))
            )
