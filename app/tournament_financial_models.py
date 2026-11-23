"""Blocked review aggregates, not fee/refund/payout authority or currency assignments."""

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from app.database import Base
from app.financial_operation_models import UUID_CHECK
from app.time import utc_now
from app.tournament_financial_schema import attach_triggers


class TournamentFinancialIntent(Base):
    __tablename__ = "tournament_financial_intents"
    __table_args__ = (
        CheckConstraint(UUID_CHECK.format("id"), name="review_uuid4"),
        CheckConstraint("kind IN ('FEE','REFUND','PAYOUT')", name="review_kind"),
        CheckConstraint("status='POLICY_REQUIRED'", name="policy_blocked"),
        CheckConstraint(
            "amount_minor IS NULL AND currency IS NULL AND operation_id IS NULL AND receipt_id IS NULL",
            name="no_unapproved_money",
        ),
        CheckConstraint(
            "(kind IN ('FEE','REFUND') AND registration_id IS NOT NULL AND result_id IS NULL) OR (kind='PAYOUT' AND result_id IS NOT NULL AND registration_id IS NULL)",
            name="review_context",
        ),
        CheckConstraint(
            "length(scope_digest)=64 AND scope_digest NOT GLOB '*[^0-9a-f]*'",
            name="scope_sha256",
        ),
        UniqueConstraint(
            "kind", "registration_id", name="uq_tournament_registration_review"
        ),
        UniqueConstraint("kind", "result_id", name="uq_tournament_result_review"),
    )
    id = Column(String(36), primary_key=True)
    kind = Column(String(12), nullable=False)
    status = Column(String(20), nullable=False, default="POLICY_REQUIRED")
    tournament_id = Column(
        Integer, ForeignKey("tournaments.id"), nullable=False, index=True
    )
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    registration_id = Column(
        Integer, ForeignKey("tournament_registrations.id"), nullable=True
    )
    result_id = Column(Integer, ForeignKey("tournament_results.id"), nullable=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scope_digest = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    amount_minor = Column(BigInteger, nullable=True)
    currency = Column(String(3), nullable=True)
    operation_id = Column(
        String(36), ForeignKey("financial_operations.id"), nullable=True
    )
    receipt_id = Column(
        String(36), ForeignKey("financial_ledger_entries.id"), nullable=True
    )


class TournamentFinancialRequest(Base):
    __tablename__ = "tournament_financial_requests"
    __table_args__ = (
        CheckConstraint(UUID_CHECK.format("idempotency_key"), name="request_uuid4"),
        CheckConstraint(
            "actor_role IN ('organiser','administrator')", name="review_role"
        ),
    )
    idempotency_key = Column(String(36), primary_key=True)
    intent_id = Column(
        String(36),
        ForeignKey("tournament_financial_intents.id"),
        nullable=False,
        index=True,
    )
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


attach_triggers(TournamentFinancialIntent.__table__)
attach_triggers(TournamentFinancialRequest.__table__)
