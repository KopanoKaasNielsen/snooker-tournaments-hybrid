"""Explicit opt-in V1 policies and immutable typed facts; no spendable pool money."""

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


class TournamentV1Policy(Base):
    __tablename__ = "tournament_v1_policies"
    __table_args__ = (
        CheckConstraint(
            "version='BWP_TOURNAMENT_V1' AND currency='BWP'", name="version_currency"
        ),
        CheckConstraint(
            "activation_state='INACTIVE' AND token_state='UNRESOLVED' AND token_direction='DEDUCT_BEFORE_PRIZES'",
            name="activation_blocked",
        ),
        CheckConstraint(
            "first_weight=60 AND second_weight=30 AND third_weight=10 AND token_numerator=1 AND token_denominator=10",
            name="approved_weights",
        ),
        CheckConstraint(
            "typeof(price_minor)='integer' AND price_minor BETWEEN 0 AND 9000000000000000",
            name="price_range",
        ),
        CheckConstraint(
            "typeof(capacity)='integer' AND capacity>0", name="positive_capacity"
        ),
        CheckConstraint(
            "registration_deadline<=commences_at AND created_at<registration_deadline",
            name="policy_dates",
        ),
    )
    id = Column(String(36), primary_key=True)
    tournament_id = Column(
        Integer, ForeignKey("tournaments.id"), nullable=False, unique=True
    )
    version = Column(String(32), nullable=False)
    currency = Column(String(3), nullable=False)
    price_minor = Column(BigInteger, nullable=False)
    capacity = Column(Integer, nullable=False)
    registration_deadline = Column(DateTime, nullable=False)
    commences_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    activation_state = Column(String(16), nullable=False, default="INACTIVE")
    token_state = Column(String(16), nullable=False, default="UNRESOLVED")
    token_direction = Column(String(32), nullable=False, default="DEDUCT_BEFORE_PRIZES")
    first_weight = Column(Integer, nullable=False, default=60)
    second_weight = Column(Integer, nullable=False, default=30)
    third_weight = Column(Integer, nullable=False, default=10)
    token_numerator = Column(Integer, nullable=False, default=1)
    token_denominator = Column(Integer, nullable=False, default=10)


class TournamentPoolAccount(Base):
    __tablename__ = "tournament_pool_accounts"
    __table_args__ = (
        CheckConstraint(
            "currency='BWP' AND state='NON_SPENDABLE' AND cleared_minor=0 AND spendable_minor=0",
            name="no_pool_money",
        ),
    )
    id = Column(String(36), primary_key=True)
    policy_id = Column(
        String(36), ForeignKey("tournament_v1_policies.id"), nullable=False, unique=True
    )
    currency = Column(String(3), nullable=False)
    state = Column(String(20), nullable=False, default="NON_SPENDABLE")
    cleared_minor = Column(BigInteger, nullable=False, default=0)
    spendable_minor = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utc_now)


KINDS = "'ELIGIBILITY','REGISTRATION','FEE_OBLIGATION','CONFIRMATION','WAIVER','FEE_REFERENCE','SPONSOR_REVIEW','CANCELLATION','REFUND_REVIEW','MATCH_RESULT','RESULTS_REVISION','RESULTS_APPROVAL','PAYOUT_SCHEDULE'"


class TournamentV1Record(Base):
    """Typed immutable facts; monetary values and references are relational, snapshots are JSON."""

    __tablename__ = "tournament_v1_records"
    __table_args__ = (
        UniqueConstraint(
            "policy_id", "kind", "identity_key", name="uq_v1_fact_identity"
        ),
        CheckConstraint(f"kind IN ({KINDS})", name="fact_kind"),
        CheckConstraint("financially_effective=0", name="no_financial_effect"),
        CheckConstraint(
            "amount_minor IS NULL OR (typeof(amount_minor)='integer' AND amount_minor BETWEEN 0 AND 9000000000000000)",
            name="fact_amount",
        ),
        CheckConstraint(
            "(kind IN ('FEE_OBLIGATION','FEE_REFERENCE','REFUND_REVIEW') AND amount_minor IS NOT NULL) OR (kind NOT IN ('FEE_OBLIGATION','FEE_REFERENCE','REFUND_REVIEW') AND amount_minor IS NULL)",
            name="amount_scope",
        ),
        CheckConstraint(
            "(kind='FEE_REFERENCE' AND operation_id IS NOT NULL AND receipt_id IS NOT NULL) OR (kind!='FEE_REFERENCE' AND operation_id IS NULL AND receipt_id IS NULL)",
            name="receipt_scope",
        ),
        CheckConstraint("json_valid(data_json)", name="valid_snapshot"),
    )
    id = Column(String(36), primary_key=True)
    policy_id = Column(
        String(36), ForeignKey("tournament_v1_policies.id"), nullable=False, index=True
    )
    kind = Column(String(24), nullable=False)
    identity_key = Column(String(100), nullable=False)
    parent_id = Column(
        String(36), ForeignKey("tournament_v1_records.id"), nullable=True, index=True
    )
    pool_id = Column(
        String(36), ForeignKey("tournament_pool_accounts.id"), nullable=True
    )
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    registration_id = Column(
        Integer, ForeignKey("tournament_registrations.id"), nullable=True
    )
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=True)
    amount_minor = Column(BigInteger, nullable=True)
    operation_id = Column(
        String(36), ForeignKey("financial_operations.id"), nullable=True, unique=True
    )
    receipt_id = Column(
        String(36),
        ForeignKey("financial_ledger_entries.id"),
        nullable=True,
        unique=True,
    )
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    data_json = Column(String, nullable=False, default="{}")
    financially_effective = Column(Integer, nullable=False, default=0)


class TournamentV1Request(Base):
    __tablename__ = "tournament_v1_requests"
    __table_args__ = (
        CheckConstraint(UUID_CHECK.format("idempotency_key"), name="v1_request_uuid"),
        CheckConstraint(
            "length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'",
            name="v1_payload_digest",
        ),
    )
    idempotency_key = Column(String(36), primary_key=True)
    policy_id = Column(
        String(36), ForeignKey("tournament_v1_policies.id"), nullable=False, index=True
    )
    record_id = Column(
        String(36), ForeignKey("tournament_v1_records.id"), nullable=True
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(32), nullable=False)
    payload_digest = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


from app.tournament_v1_schema import attach_v1_triggers

for model in (
    TournamentV1Policy,
    TournamentPoolAccount,
    TournamentV1Record,
    TournamentV1Request,
):
    attach_v1_triggers(model.__table__)
