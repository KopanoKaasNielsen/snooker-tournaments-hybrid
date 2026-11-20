"""Additive, exact BWP operation intents and append-only transition audit."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from app.database import Base
from app.time import utc_now

STATES = "'PENDING','VERIFIED','POSTED','REJECTED','CANCELLED'"
UUID_CHECK = "length({0}) = 36 AND substr({0},9,1)='-' AND substr({0},14,1)='-' AND substr({0},19,1)='-' AND substr({0},24,1)='-' AND substr({0},15,1)='4' AND substr({0},20,1) IN ('8','9','a','b') AND length(replace({0},'-',''))=32 AND replace({0},'-','') NOT GLOB '*[^0-9a-f]*'"
EVIDENCE = (
    "provider",
    "provider_event_digest",
    "provider_payload_digest",
    "reference_digest",
    "verified_at",
    "verified_by_id",
)
COMPLETE = " AND ".join(f"{name} IS NOT NULL" for name in EVIDENCE)
EMPTY = " AND ".join(f"{name} IS NULL" for name in EVIDENCE)


class FinancialOperation(Base):
    __tablename__ = "financial_operations"
    __table_args__ = (
        CheckConstraint(UUID_CHECK.format("id"), name="operation_uuid4"),
        CheckConstraint(UUID_CHECK.format("idempotency_key"), name="request_uuid4"),
        CheckConstraint("currency = 'BWP'", name="currency_bwp"),
        CheckConstraint(
            "provider IS NULL OR (length(provider) BETWEEN 1 AND 32 AND provider NOT GLOB '*[^a-z0-9_-]*')",
            name="provider_identifier",
        ),
        CheckConstraint(
            "typeof(amount_minor)='integer' AND amount_minor BETWEEN 1 AND 9000000000000000",
            name="amount_range",
        ),
        CheckConstraint(
            "kind IN ('deposit','withdrawal','fee','prize')", name="operation_kind"
        ),
        CheckConstraint(f"status IN ({STATES})", name="operation_state"),
        CheckConstraint(f"({COMPLETE}) OR ({EMPTY})", name="evidence_completeness"),
        CheckConstraint(
            f"(status='PENDING' AND {EMPTY} AND receipt_id IS NULL AND posted_at IS NULL AND posted_by_id IS NULL AND rejected_at IS NULL AND cancelled_at IS NULL) OR (status='VERIFIED' AND {COMPLETE} AND receipt_id IS NULL AND posted_at IS NULL AND posted_by_id IS NULL AND rejected_at IS NULL AND cancelled_at IS NULL) OR (status='POSTED' AND {COMPLETE} AND receipt_id IS NOT NULL AND posted_at IS NOT NULL AND posted_by_id IS NOT NULL AND rejected_at IS NULL AND cancelled_at IS NULL) OR (status='REJECTED' AND rejected_at IS NOT NULL AND receipt_id IS NULL AND posted_at IS NULL AND posted_by_id IS NULL AND cancelled_at IS NULL) OR (status='CANCELLED' AND {EMPTY} AND cancelled_at IS NOT NULL AND receipt_id IS NULL AND posted_at IS NULL AND posted_by_id IS NULL AND rejected_at IS NULL)",
            name="state_fields",
        ),
        UniqueConstraint(
            "provider", "provider_event_digest", name="uq_operation_provider_event"
        ),
        *[
            CheckConstraint(
                f"{name} IS NULL OR (length({name})=64 AND {name} NOT GLOB '*[^0-9a-f]*')",
                name=f"{name}_sha256",
            )
            for name in (
                "provider_event_digest",
                "provider_payload_digest",
                "reference_digest",
            )
        ],
    )
    id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(36), unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    wallet_id = Column(
        String(36), ForeignKey("financial_wallets.id"), nullable=False, index=True
    )
    amount_minor = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(12), nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now)
    last_actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider = Column(String(32), nullable=True)
    provider_event_digest = Column(String(64), nullable=True)
    provider_payload_digest = Column(String(64), nullable=True)
    reference_digest = Column(String(64), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    posted_at = Column(DateTime, nullable=True)
    posted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    receipt_id = Column(
        String(36),
        ForeignKey("financial_ledger_entries.id"),
        unique=True,
        nullable=True,
    )


class FinancialOperationAudit(Base):
    __tablename__ = "financial_operation_audit"
    __table_args__ = (
        UniqueConstraint("operation_id", "event", name="uq_operation_audit_event"),
        CheckConstraint(
            "event IN ('created','verified','posted','rejected','cancelled')",
            name="audit_event",
        ),
        CheckConstraint(
            "reason_code IN ('requested','evidence_verified','posted','policy_rejected','owner_cancelled','admin_cancelled')",
            name="audit_reason",
        ),
        CheckConstraint(f"to_status IN ({STATES})", name="audit_state"),
        CheckConstraint(
            "actor_role IN ('player','organiser','administrator')", name="audit_role"
        ),
    )
    id = Column(String(36), primary_key=True)
    operation_id = Column(
        String(36), ForeignKey("financial_operations.id"), nullable=False, index=True
    )
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(20), nullable=False)
    event = Column(String(16), nullable=False)
    reason_code = Column(String(32), nullable=False)
    from_status = Column(String(12), nullable=True)
    to_status = Column(String(12), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


from app.operation_schema import attach_operation_triggers

attach_operation_triggers(FinancialOperation.__table__)
attach_operation_triggers(FinancialOperationAudit.__table__)
