"""Inactive V1 tournament orchestration. No method creates or posts financial operations."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from app.models import (
    Tournament,
    TournamentOrganiser,
    TournamentRegistration,
    TournamentStatus,
    Match,
    User,
    FinancialOperation,
    FinancialLedgerEntry,
    TournamentV1Policy,
    TournamentPoolAccount,
    TournamentV1Record,
    TournamentV1Request,
)
from app.security import tournament_permission
from app.time import utc_now
from app.services.tournament_financials import (
    TournamentFinancialService,
    TournamentPolicyRequired,
)
from app.services.financial_operations import OperationDenied, OperationConflict
from app.services.financial_wallets import FinancialError, _key
from app.tournament_v1_schema import triggers_match
from app.tournament_financial_schema import key_reserved
from app.tournament_prize_preview import VERSION, PreviewWinner, allocate_preview, minor
from app.money import require_currency


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def evidence(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Evidence must be a SHA-256 reference, never credentials")
    return value


class TournamentV1Service:
    def __init__(self, engine):
        self.reviews = TournamentFinancialService(engine)
        self.operations = self.reviews.operations

    @contextmanager
    def _transaction(self, *, write):
        with self.reviews._transaction(write=write) as db:
            if not triggers_match(db.connection()):
                raise FinancialError("V1 integrity triggers missing or changed")
            yield db

    def _context(self, db, token, policy_id, *, staff=False, admin=False):
        actor = self.operations._actor(db, token)
        policy = db.get(TournamentV1Policy, policy_id)
        if policy is None:
            raise OperationDenied("Policy unavailable")
        if staff or admin:
            tournament_permission(db, actor, policy.tournament_id)
        if admin and actor.role != "administrator":
            raise OperationDenied("Independent administrator required")
        return actor, policy

    def _id(self, db):
        key = str(uuid4())
        if key_reserved(db.connection(), key) or self.reviews._money_key_exists(
            db, key
        ):
            raise OperationConflict("Identity collision; retry")
        return key

    def _begin(self, db, actor, action, payload, key):
        _key(key)
        previous = db.get(TournamentV1Request, key)
        if previous:
            if (previous.actor_id, previous.action, previous.payload_digest) != (
                actor.id,
                action,
                digest(payload),
            ):
                raise OperationConflict(
                    "Idempotency key has a different actor or payload"
                )
            return previous
        if key_reserved(db.connection(), key) or self.reviews._money_key_exists(
            db, key
        ):
            raise OperationConflict(
                "Idempotency key reserved by another financial identity"
            )
        return None

    def _end(self, db, actor, policy, action, payload, key, record=None):
        db.add(
            TournamentV1Request(
                idempotency_key=key,
                policy_id=policy.id,
                record_id=record.id if record else None,
                actor_id=actor.id,
                action=action,
                payload_digest=digest(payload),
            )
        )
        db.flush()
        return record.id if record else policy.id

    @staticmethod
    def _find(db, p, kind, identity):
        return db.scalar(
            select(TournamentV1Record).where(
                TournamentV1Record.policy_id == p.id,
                TournamentV1Record.kind == kind,
                TournamentV1Record.identity_key == str(identity),
            )
        )

    @staticmethod
    def _records(db, p, kind):
        return db.scalars(
            select(TournamentV1Record)
            .where(
                TournamentV1Record.policy_id == p.id, TournamentV1Record.kind == kind
            )
            .order_by(TournamentV1Record.created_at, TournamentV1Record.id)
        ).all()

    def _fact(self, db, p, actor, kind, identity, *, data=None, **fields):
        row = TournamentV1Record(
            id=self._id(db),
            policy_id=p.id,
            kind=kind,
            identity_key=str(identity),
            created_by_id=actor.id,
            data_json=encoded(data or {}),
            **fields,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def _row(db, p, record_id, kind):
        row = db.get(TournamentV1Record, record_id)
        if row is None or row.policy_id != p.id or row.kind != kind:
            raise OperationDenied("Review context unavailable")
        return row

    def create_tournament(
        self,
        token,
        *,
        name,
        price_minor,
        currency,
        capacity,
        registration_deadline,
        commences_at,
        idempotency_key,
    ):
        require_currency(currency)
        minor(price_minor)
        if (
            type(capacity) is not int
            or capacity < 1
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError("Name and positive integer capacity required")
        if any(
            not isinstance(d, datetime) or d.tzinfo is not None
            for d in (registration_deadline, commences_at)
        ):
            raise ValueError("Naive UTC deadlines required")
        payload = dict(
            name=name,
            price_minor=price_minor,
            currency=currency,
            capacity=capacity,
            deadline=registration_deadline.isoformat(),
            starts=commences_at.isoformat(),
        )
        with self._transaction(write=True) as db:
            actor = self.operations._actor(db, token)
            if actor.role not in ("administrator", "organiser"):
                raise OperationDenied("Tournament creation requires organiser")
            old = self._begin(db, actor, "CREATE", payload, idempotency_key)
            if old:
                return old.policy_id
            now = utc_now()
            if not now < registration_deadline <= commences_at:
                raise ValueError(
                    "Future registration deadline at or before commencement required"
                )
            tournament = Tournament(
                name=name, entry_fee=0, date=commences_at, created_at=now
            )
            db.add(tournament)
            db.flush()
            p = TournamentV1Policy(
                id=self._id(db),
                tournament_id=tournament.id,
                version=VERSION,
                currency=currency,
                price_minor=price_minor,
                capacity=capacity,
                registration_deadline=registration_deadline,
                commences_at=commences_at,
                created_by_id=actor.id,
                created_at=now,
            )
            db.add(p)
            db.flush()
            db.add_all(
                [
                    TournamentOrganiser(tournament_id=tournament.id, user_id=actor.id),
                    TournamentPoolAccount(
                        id=self._id(db), policy_id=p.id, currency=currency
                    ),
                ]
            )
            return self._end(db, actor, p, "CREATE", payload, idempotency_key)

    def approve_eligibility(
        self, token, policy_id, owner_id, *, evidence_digest, idempotency_key
    ):
        evidence(evidence_digest)
        payload = dict(policy=policy_id, owner=owner_id, evidence=evidence_digest)
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "ELIGIBILITY", payload, idempotency_key)
            if old:
                return old.record_id
            owner = db.get(User, owner_id)
            if (
                owner is None
                or not owner.is_active
                or owner.player_id is None
                or actor.id == owner.id
            ):
                raise OperationDenied(
                    "Independent eligibility review of an active linked player required"
                )
            row = self._find(db, p, "ELIGIBILITY", owner.id)
            if row and json.loads(row.data_json)["evidence_digest"] != evidence_digest:
                raise OperationConflict("Eligibility evidence already locked")
            if row is None:
                row = self._fact(
                    db,
                    p,
                    actor,
                    "ELIGIBILITY",
                    owner.id,
                    owner_id=owner.id,
                    player_id=owner.player_id,
                    data={"evidence_digest": evidence_digest, "basis": "MANUAL_REVIEW"},
                )
            return self._end(db, actor, p, "ELIGIBILITY", payload, idempotency_key, row)

    def register(self, token, policy_id, *, idempotency_key):
        payload = {"policy": policy_id}
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id)
            old = self._begin(db, actor, "REGISTER", payload, idempotency_key)
            if old:
                return old.record_id
            row = self._find(db, p, "REGISTRATION", actor.id)
            if row is None:
                eligible = self._find(db, p, "ELIGIBILITY", actor.id)
                if (
                    eligible is None
                    or eligible.player_id != actor.player_id
                    or actor.player_id is None
                ):
                    raise OperationDenied(
                        "Current linked player eligibility review required"
                    )
                if utc_now() > p.registration_deadline or self._find(
                    db, p, "CANCELLATION", "singleton"
                ):
                    raise OperationDenied("Registration closed")
                if len(self._records(db, p, "REGISTRATION")) >= p.capacity:
                    raise OperationConflict("Tournament capacity reached")
                legacy = TournamentRegistration(
                    tournament_id=p.tournament_id,
                    player_id=actor.player_id,
                    paid=False,
                    waived=False,
                    contribution=0,
                )
                db.add(legacy)
                db.flush()
                row = self._fact(
                    db,
                    p,
                    actor,
                    "REGISTRATION",
                    actor.id,
                    parent_id=eligible.id,
                    owner_id=actor.id,
                    player_id=actor.player_id,
                    registration_id=legacy.id,
                )
                self._fact(
                    db,
                    p,
                    actor,
                    "FEE_OBLIGATION",
                    row.id,
                    parent_id=row.id,
                    owner_id=actor.id,
                    player_id=actor.player_id,
                    registration_id=legacy.id,
                    amount_minor=p.price_minor,
                )
                if p.price_minor == 0:
                    self._confirm(db, p, actor, row, "FREE")
            return self._end(db, actor, p, "REGISTER", payload, idempotency_key, row)

    def _confirm(self, db, p, actor, row, basis):
        return self._fact(
            db,
            p,
            actor,
            "CONFIRMATION",
            row.id,
            parent_id=row.id,
            owner_id=row.owner_id,
            player_id=row.player_id,
            registration_id=row.registration_id,
            data={"basis": basis},
        )

    def approve_waiver(
        self, token, policy_id, registration_id, *, evidence_digest, idempotency_key
    ):
        evidence(evidence_digest)
        payload = dict(
            policy=policy_id, registration=registration_id, evidence=evidence_digest
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, admin=True)
            old = self._begin(db, actor, "WAIVER", payload, idempotency_key)
            if old:
                return old.record_id
            reg = self._row(db, p, registration_id, "REGISTRATION")
            if actor.id == reg.owner_id:
                raise OperationDenied("Independent waiver approval required")
            row = self._find(db, p, "WAIVER", reg.id)
            if row and json.loads(row.data_json)["evidence_digest"] != evidence_digest:
                raise OperationConflict("Waiver evidence already locked")
            if row is None:
                fee = self._find(db, p, "FEE_OBLIGATION", reg.id)
                if (
                    p.price_minor == 0
                    or utc_now() > p.registration_deadline
                    or self._find(db, p, "CONFIRMATION", reg.id)
                    or self._find(db, p, "FEE_REFERENCE", fee.id)
                    or self._find(db, p, "CANCELLATION", "singleton")
                ):
                    raise OperationDenied("Waiver unavailable for this registration")
                row = self._fact(
                    db,
                    p,
                    actor,
                    "WAIVER",
                    reg.id,
                    parent_id=reg.id,
                    owner_id=reg.owner_id,
                    player_id=reg.player_id,
                    data={"evidence_digest": evidence_digest},
                )
                self._confirm(db, p, actor, reg, "WAIVER")
            return self._end(db, actor, p, "WAIVER", payload, idempotency_key, row)

    def review_posted_fee_reference(
        self, token, policy_id, obligation_id, operation_id, *, idempotency_key
    ):
        payload = dict(
            policy=policy_id, obligation=obligation_id, operation=operation_id
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, admin=True)
            old = self._begin(db, actor, "FEE_REFERENCE", payload, idempotency_key)
            if old:
                return old.record_id
            fee = self._row(db, p, obligation_id, "FEE_OBLIGATION")
            reg = self._row(db, p, fee.parent_id, "REGISTRATION")
            op = db.get(FinancialOperation, operation_id)
            if (
                op is None
                or op.status != "POSTED"
                or op.kind != "fee"
                or op.currency != "BWP"
                or op.amount_minor != fee.amount_minor
                or op.owner_id != reg.owner_id
                or actor.id in (op.owner_id, op.requested_by_id)
                or op.created_at < reg.created_at
                or op.posted_at < reg.created_at
            ):
                raise OperationDenied(
                    "Independent posted fee provenance required; clearing is not inferred"
                )
            receipt = db.get(FinancialLedgerEntry, op.receipt_id)
            if receipt is None or (
                receipt.idempotency_key,
                receipt.wallet_id,
                receipt.amount_minor,
                receipt.kind,
            ) != (op.id, op.wallet_id, op.amount_minor, "fee"):
                raise OperationConflict("Operation receipt mismatch")
            if self._find(db, p, "CONFIRMATION", reg.id):
                raise OperationDenied(
                    "Free or waived registration cannot fund the pool"
                )
            row = self._find(db, p, "FEE_REFERENCE", fee.id)
            if row and row.operation_id != op.id:
                raise OperationConflict("Fee reference already locked")
            if row is None:
                pool = db.scalar(
                    select(TournamentPoolAccount).where(
                        TournamentPoolAccount.policy_id == p.id
                    )
                )
                row = self._fact(
                    db,
                    p,
                    actor,
                    "FEE_REFERENCE",
                    fee.id,
                    parent_id=fee.id,
                    pool_id=pool.id,
                    owner_id=reg.owner_id,
                    player_id=reg.player_id,
                    amount_minor=op.amount_minor,
                    operation_id=op.id,
                    receipt_id=receipt.id,
                    data={"cleared": False, "basis": "POSTED_DEBIT_REFERENCE_ONLY"},
                )
            return self._end(
                db, actor, p, "FEE_REFERENCE", payload, idempotency_key, row
            )

    def review_sponsorship(self, token, policy_id, *, evidence_digest, idempotency_key):
        evidence(evidence_digest)
        payload = dict(policy=policy_id, evidence=evidence_digest)
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, admin=True)
            old = self._begin(db, actor, "SPONSOR_REVIEW", payload, idempotency_key)
            if old:
                return old.record_id
            row = self._find(db, p, "SPONSOR_REVIEW", evidence_digest)
            if row is None:
                pool = db.scalar(
                    select(TournamentPoolAccount).where(
                        TournamentPoolAccount.policy_id == p.id
                    )
                )
                row = self._fact(
                    db,
                    p,
                    actor,
                    "SPONSOR_REVIEW",
                    evidence_digest,
                    pool_id=pool.id,
                    data={
                        "evidence_digest": evidence_digest,
                        "blocked": "NO_SPONSORSHIP_CLEARING_OPERATION",
                    },
                )
            return self._end(
                db, actor, p, "SPONSOR_REVIEW", payload, idempotency_key, row
            )

    def request_refund_review(
        self, token, policy_id, fee_reference_id, *, amount_minor, idempotency_key
    ):
        minor(amount_minor, positive=True)
        payload = dict(
            policy=policy_id, fee=fee_reference_id, amount_minor=amount_minor
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id)
            fee = self._row(db, p, fee_reference_id, "FEE_REFERENCE")
            if fee.owner_id != actor.id:
                raise OperationDenied("Original fee owner consent required")
            old = self._begin(db, actor, "REFUND_REVIEW", payload, idempotency_key)
            if old:
                return old.record_id
            reviewed = sum(
                r.amount_minor
                for r in self._records(db, p, "REFUND_REVIEW")
                if r.parent_id == fee.id
            )
            if amount_minor > fee.amount_minor - reviewed:
                raise OperationConflict(
                    "Refund reviews exceed remaining original principal"
                )
            row = self._fact(
                db,
                p,
                actor,
                "REFUND_REVIEW",
                idempotency_key,
                parent_id=fee.id,
                owner_id=actor.id,
                player_id=fee.player_id,
                amount_minor=amount_minor,
                data={
                    "status": "REVIEW_ONLY",
                    "refunded_minor": 0,
                    "reason_policy": "UNRESOLVED",
                },
            )
            return self._end(
                db, actor, p, "REFUND_REVIEW", payload, idempotency_key, row
            )

    def cancel_before_start(
        self, token, policy_id, *, evidence_digest, idempotency_key
    ):
        evidence(evidence_digest)
        payload = dict(policy=policy_id, evidence=evidence_digest)
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "CANCEL", payload, idempotency_key)
            if old:
                return old.record_id
            row = self._find(db, p, "CANCELLATION", "singleton")
            if row and json.loads(row.data_json)["evidence_digest"] != evidence_digest:
                raise OperationConflict("Cancellation already reviewed")
            if row is None:
                if utc_now() >= p.commences_at:
                    raise TournamentPolicyRequired(
                        "Late cancellation policy unresolved"
                    )
                row = self._fact(
                    db,
                    p,
                    actor,
                    "CANCELLATION",
                    "singleton",
                    data={
                        "evidence_digest": evidence_digest,
                        "recommendation": "FULL_REMAINING_PRINCIPAL",
                        "automatic_refund": False,
                    },
                )
                db.get(Tournament, p.tournament_id).status = TournamentStatus.CANCELLED
            return self._end(db, actor, p, "CANCEL", payload, idempotency_key, row)

    def create_match(
        self, token, policy_id, player1_id, player2_id, *, idempotency_key
    ):
        payload = dict(policy=policy_id, player1=player1_id, player2=player2_id)
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "MATCH", payload, idempotency_key)
            if old:
                return json.loads(db.get(TournamentV1Record, old.record_id).data_json)[
                    "match_id"
                ]
            confirmed = {r.player_id for r in self._records(db, p, "CONFIRMATION")}
            if (
                player1_id not in confirmed
                or (
                    player2_id is not None
                    and (player2_id not in confirmed or player2_id == player1_id)
                )
                or self._find(db, p, "CANCELLATION", "singleton")
            ):
                raise OperationDenied(
                    "Distinct confirmed tournament participants required"
                )
            if self._records(db, p, "RESULTS_REVISION"):
                raise OperationDenied("Match roster is locked by a results revision")
            match = Match(
                tournament_id=p.tournament_id,
                player1_id=player1_id,
                player2_id=player2_id,
            )
            db.add(match)
            db.flush()
            row = self._fact(
                db,
                p,
                actor,
                "MATCH_RESULT",
                "create:" + str(match.id),
                match_id=match.id,
                data={"match_id": match.id, "action": "CREATE"},
            )
            self._end(db, actor, p, "MATCH", payload, idempotency_key, row)
            return match.id

    def submit_result(
        self,
        token,
        policy_id,
        match_id,
        score1,
        score2,
        *,
        evidence_digest,
        idempotency_key,
        correction_digest=None,
    ):
        evidence(evidence_digest)
        if correction_digest is not None:
            evidence(correction_digest)
        payload = dict(
            policy=policy_id,
            match=match_id,
            score1=score1,
            score2=score2,
            evidence=evidence_digest,
            correction=correction_digest,
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "RESULT", payload, idempotency_key)
            if old:
                return old.record_id
            match = db.get(Match, match_id)
            if match is None or match.tournament_id != p.tournament_id:
                raise OperationDenied("Match unavailable")
            if utc_now() < p.commences_at or self._find(
                db, p, "CANCELLATION", "singleton"
            ):
                raise OperationDenied("Tournament has not commenced or is cancelled")
            if self._records(db, p, "RESULTS_REVISION") and correction_digest is None:
                raise OperationDenied(
                    "Locked revision requires explicit correction evidence and new review"
                )
            if any(type(s) is not int or s < 0 for s in (score1, score2)):
                raise ValueError("Non-negative integer scores required")
            if match.player2_id is None:
                if (score1, score2) != (0, 0):
                    raise ValueError("Bye has no played frames")
                winner = match.player1_id
            else:
                if max(score1, score2) != 2 or min(score1, score2) >= 2:
                    raise ValueError("Decisive best-of-three result required")
                winner = match.player1_id if score1 > score2 else match.player2_id
            before = self._match_snapshot(match)
            (
                match.score_player1,
                match.score_player2,
                match.winner_id,
                match.completed_at,
            ) = (score1, score2, winner, utc_now())
            row = self._fact(
                db,
                p,
                actor,
                "MATCH_RESULT",
                idempotency_key,
                match_id=match.id,
                data={
                    "match_id": match.id,
                    "action": "RESULT",
                    "before": before,
                    "after": self._match_snapshot(match),
                    "evidence_digest": evidence_digest,
                    "correction_digest": correction_digest,
                },
            )
            return self._end(db, actor, p, "RESULT", payload, idempotency_key, row)

    @staticmethod
    def _match_snapshot(m):
        return dict(
            id=m.id,
            p1=m.player1_id,
            p2=m.player2_id,
            winner=m.winner_id,
            s1=m.score_player1,
            s2=m.score_player2,
            completed=m.completed_at.isoformat() if m.completed_at else None,
        )

    def _standings(self, db, p, winners, final_id, third_id=None):
        if utc_now() < p.commences_at or self._find(db, p, "CANCELLATION", "singleton"):
            raise OperationDenied("Active commenced tournament required")
        confirmations = self._records(db, p, "CONFIRMATION")
        members = {r.player_id for r in confirmations}
        if (
            not members
            or len(winners) != min(3, len(members))
            or len(set(winners)) != len(winners)
            or not set(winners) <= members
        ):
            raise ValueError(
                "Unique confirmed eligible winners for all applicable positions required"
            )
        for reg in self._records(db, p, "REGISTRATION"):
            owner = db.get(User, reg.owner_id)
            if owner is None or not owner.is_active or owner.player_id != reg.player_id:
                raise OperationDenied("Membership/eligibility changed; review required")
        matches = db.scalars(
            select(Match)
            .where(Match.tournament_id == p.tournament_id)
            .order_by(Match.id)
        ).all()
        active = set(members)
        regular = []
        result_facts = self._records(db, p, "MATCH_RESULT")
        proposers = set()
        for m in matches:
            snapshot = self._match_snapshot(m)
            sources = [
                r
                for r in result_facts
                if r.match_id == m.id
                and json.loads(r.data_json).get("action") == "RESULT"
            ]
            if not sources or json.loads(sources[-1].data_json)["after"] != snapshot:
                raise OperationConflict(
                    "Match lacks authoritative reviewed result or was changed outside workflow"
                )
            proposers.add(sources[-1].created_by_id)
            participants = {x for x in (m.player1_id, m.player2_id) if x is not None}
            if (
                not participants <= members
                or m.winner_id not in participants
                or m.completed_at is None
            ):
                raise ValueError("Incomplete or invalid match membership")
            if m.player2_id is not None and (
                m.player1_id == m.player2_id
                or max(m.score_player1, m.score_player2) != 2
                or min(m.score_player1, m.score_player2) >= 2
                or m.winner_id
                != (m.player1_id if m.score_player1 > m.score_player2 else m.player2_id)
            ):
                raise ValueError("Ties or inconsistent decisive result")
            if m.player2_id is None and (m.score_player1, m.score_player2) != (0, 0):
                raise ValueError("Invalid bye")
            if m.id == third_id:
                continue
            if not participants <= active:
                raise ValueError(
                    "Eliminated participant returned or bracket unresolved"
                )
            if len(participants) == 2:
                active -= participants - {m.winner_id}
                regular.append(m)
        if len(members) == 1:
            if regular or final_id is not None or active != {winners[0]}:
                raise ValueError("Single-player results do not have a played final")
        else:
            if (
                len(regular) != len(members) - 1
                or not regular
                or regular[-1].id != final_id
                or active != {winners[0]}
            ):
                raise ValueError("Required knockout matches/final unresolved")
            final = regular[-1]
            if winners[1] not in {final.player1_id, final.player2_id} - {
                final.winner_id
            }:
                raise ValueError("Runner-up does not match decisive final")
        if len(winners) == 3:
            if len(members) == 3:
                if third_id is not None or set(winners) != members:
                    raise ValueError("Third place unresolved")
            else:
                third = next((m for m in matches if m.id == third_id), None)
                if (
                    third is None
                    or third.winner_id != winners[2]
                    or winners[0] in (third.player1_id, third.player2_id)
                    or winners[1] in (third.player1_id, third.player2_id)
                ):
                    raise ValueError("Explicit decisive third-place match required")
                semifinal_losers = set()
                for finalist in (regular[-1].player1_id, regular[-1].player2_id):
                    prior = [m for m in regular[:-1] if m.winner_id == finalist]
                    if not prior:
                        raise ValueError(
                            "Third-place eligibility requires decisive semifinal provenance"
                        )
                    semi = prior[-1]
                    semifinal_losers.update(
                        {semi.player1_id, semi.player2_id} - {semi.winner_id}
                    )
                if (
                    len(semifinal_losers) != 2
                    or None in semifinal_losers
                    or {third.player1_id, third.player2_id} != semifinal_losers
                ):
                    raise ValueError(
                        "Third-place match must resolve the two semifinal losers"
                    )

        elif third_id is not None:
            raise ValueError("Unexpected third-place match")
        return dict(
            winners=[dict(player_id=x, position=i + 1) for i, x in enumerate(winners)],
            matches=[self._match_snapshot(m) for m in matches],
            members=sorted(members),
            final_id=final_id,
            third_id=third_id,
            proposers=sorted(proposers),
        )

    def lock_results(
        self,
        token,
        policy_id,
        winners,
        *,
        final_match_id=None,
        third_match_id=None,
        evidence_digest,
        idempotency_key,
    ):
        evidence(evidence_digest)
        payload = dict(
            policy=policy_id,
            winners=list(winners),
            final=final_match_id,
            third=third_match_id,
            evidence=evidence_digest,
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "LOCK_RESULTS", payload, idempotency_key)
            if old:
                return old.record_id
            snapshot = self._standings(db, p, winners, final_match_id, third_match_id)
            previous = self._records(db, p, "RESULTS_REVISION")
            snapshot.update(evidence_digest=evidence_digest, revision=len(previous) + 1)
            row = self._fact(
                db,
                p,
                actor,
                "RESULTS_REVISION",
                str(len(previous) + 1),
                parent_id=previous[-1].id if previous else None,
                data=snapshot,
            )
            return self._end(
                db, actor, p, "LOCK_RESULTS", payload, idempotency_key, row
            )

    def _current_revision(self, db, p, row):
        latest = self._records(db, p, "RESULTS_REVISION")[-1]
        if latest.id != row.id:
            raise OperationConflict("Superseded results revision")
        data = json.loads(row.data_json)
        current = self._standings(
            db,
            p,
            [w["player_id"] for w in data["winners"]],
            data["final_id"],
            data["third_id"],
        )
        if any(data[k] != v for k, v in current.items()):
            raise OperationConflict(
                "Results changed; a new reviewed revision is required"
            )
        return data

    def approve_results(self, token, policy_id, revision_id, *, idempotency_key):
        payload = dict(policy=policy_id, revision=revision_id)
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, admin=True)
            old = self._begin(db, actor, "APPROVE_RESULTS", payload, idempotency_key)
            if old:
                return old.record_id
            revision = self._row(db, p, revision_id, "RESULTS_REVISION")
            data = self._current_revision(db, p, revision)
            if (
                actor.id == revision.created_by_id
                or actor.id in data["proposers"]
                or actor.player_id in [w["player_id"] for w in data["winners"]]
            ):
                raise OperationDenied(
                    "Independent non-beneficiary administrator required"
                )
            row = self._find(db, p, "RESULTS_APPROVAL", revision.id)
            if row is None:
                row = self._fact(
                    db, p, actor, "RESULTS_APPROVAL", revision.id, parent_id=revision.id
                )
            return self._end(
                db, actor, p, "APPROVE_RESULTS", payload, idempotency_key, row
            )

    def payout_schedule_preview(
        self,
        token,
        policy_id,
        revision_id,
        *,
        hypothetical_distributable_minor,
        idempotency_key,
    ):
        minor(hypothetical_distributable_minor)
        payload = dict(
            policy=policy_id,
            revision=revision_id,
            hypothetical_distributable_minor=hypothetical_distributable_minor,
        )
        with self._transaction(write=True) as db:
            actor, p = self._context(db, token, policy_id, staff=True)
            old = self._begin(db, actor, "PAYOUT_PREVIEW", payload, idempotency_key)
            if old:
                return old.record_id
            revision = self._row(db, p, revision_id, "RESULTS_REVISION")
            data = self._current_revision(db, p, revision)
            if self._find(db, p, "RESULTS_APPROVAL", revision.id) is None:
                raise OperationDenied("Independent results approval required")
            preview = asdict(
                allocate_preview(
                    hypothetical_distributable_minor,
                    tuple(PreviewWinner(**w) for w in data["winners"]),
                    currency=p.currency,
                )
            )
            row = self._find(db, p, "PAYOUT_SCHEDULE", revision.id)
            if row and row.data_json != encoded(preview):
                raise OperationConflict(
                    "One immutable scenario schedule per revision; use pure calculator for other scenarios"
                )
            if row is None:
                row = self._fact(
                    db,
                    p,
                    actor,
                    "PAYOUT_SCHEDULE",
                    revision.id,
                    parent_id=revision.id,
                    data=preview,
                )
            return self._end(
                db, actor, p, "PAYOUT_PREVIEW", payload, idempotency_key, row
            )

    def monetary_action(self, token, policy_id):
        with self._transaction(write=False) as db:
            self._context(db, token, policy_id, staff=True)
        raise TournamentPolicyRequired(
            "INACTIVE: token policy unresolved; cleared pool custody, transfers, sponsorship and refund operations unsupported. No posting, paid confirmation or token deduction permitted."
        )

    def reconcile(self, token, policy_id):
        with self._transaction(write=False) as db:
            _, p = self._context(db, token, policy_id, admin=True)
            issues = []
            pool = db.scalar(
                select(TournamentPoolAccount).where(
                    TournamentPoolAccount.policy_id == p.id
                )
            )
            if pool is None or (
                pool.currency,
                pool.cleared_minor,
                pool.spendable_minor,
                pool.state,
            ) != ("BWP", 0, 0, "NON_SPENDABLE"):
                issues.append("pool_integrity")
            facts = db.scalars(
                select(TournamentV1Record).where(TournamentV1Record.policy_id == p.id)
            ).all()
            for reg in [r for r in facts if r.kind == "REGISTRATION"]:
                fees = [
                    r
                    for r in facts
                    if r.kind == "FEE_OBLIGATION" and r.parent_id == reg.id
                ]
                if len(fees) != 1 or fees[0].amount_minor != p.price_minor:
                    issues.append("fee_obligation_mismatch")
                legacy = db.get(TournamentRegistration, reg.registration_id)
                if (
                    legacy is None
                    or legacy.player_id != reg.player_id
                    or legacy.tournament_id != p.tournament_id
                    or legacy.paid
                    or legacy.contribution != 0
                ):
                    issues.append("registration_source_changed")
            observed = 0
            for row in facts:
                if row.financially_effective != 0:
                    issues.append("unexpected_financial_effect")
                if row.kind == "FEE_REFERENCE":
                    observed += row.amount_minor
                    op = db.get(FinancialOperation, row.operation_id)
                    receipt = db.get(FinancialLedgerEntry, row.receipt_id)
                    if (
                        op is None
                        or receipt is None
                        or (
                            op.status,
                            op.kind,
                            op.currency,
                            op.amount_minor,
                            op.owner_id,
                            op.receipt_id,
                        )
                        != (
                            "POSTED",
                            "fee",
                            "BWP",
                            row.amount_minor,
                            row.owner_id,
                            row.receipt_id,
                        )
                        or (
                            receipt.idempotency_key,
                            receipt.wallet_id,
                            receipt.kind,
                            receipt.amount_minor,
                        )
                        != (op.id, op.wallet_id, "fee", row.amount_minor)
                    ):
                        issues.append("fee_provenance_mismatch")
                    if (
                        sum(
                            r.amount_minor
                            for r in facts
                            if r.kind == "REFUND_REVIEW" and r.parent_id == row.id
                        )
                        > row.amount_minor
                    ):
                        issues.append("refund_principal_exceeded")
                if row.kind == "RESULTS_REVISION":
                    try:
                        self._current_revision(db, p, row)
                    except (ValueError, OperationDenied, OperationConflict):
                        issues.append("results_revision_stale")
                if row.kind == "PAYOUT_SCHEDULE":
                    data = json.loads(row.data_json)
                    if (
                        data.get("postable") is not False
                        or sum(s["amount_minor"] for s in data["shares"])
                        != data["hypothetical_distributable_minor"]
                    ):
                        issues.append("preview_integrity")
                if self.reviews._money_key_exists(db, row.id):
                    issues.append("blocked_identity_posted")
            requests = db.scalars(
                select(TournamentV1Request).where(TournamentV1Request.policy_id == p.id)
            ).all()
            if any(
                self.reviews._money_key_exists(db, r.idempotency_key) for r in requests
            ):
                issues.append("blocked_request_posted")
            return dict(
                policy_version=p.version,
                currency=p.currency,
                activation_state=p.activation_state,
                token_state=p.token_state,
                observed_posted_debits_minor=observed,
                cleared_pool_minor=0,
                spendable_pool_minor=0,
                refunded_minor=0,
                monetary_flow_ready=False,
                issues=tuple(sorted(set(issues))),
            )
