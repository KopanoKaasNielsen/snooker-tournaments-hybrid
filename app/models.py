"""Database models for the snooker tournaments application."""

from __future__ import annotations

import enum
from app.time import utc_now

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class TournamentType(str, enum.Enum):
    """Supported tournament formats."""

    league = "league"
    knockout = "knockout"
    double_elimination = "double_elimination"


class TournamentStatus(str, enum.Enum):
    """Lifecycle state for a tournament."""

    PENDING = "PENDING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransactionType(str, enum.Enum):
    """Allowed wallet transaction types."""

    deposit = "deposit"
    withdrawal = "withdrawal"
    prize = "prize"
    fee = "fee"


class Player(Base):
    """Registered snooker player."""

    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    rating = Column(Integer, default=1500, nullable=False)
    elo = Column(Integer, default=1500, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    registrations = relationship(
        "TournamentRegistration",
        back_populates="player",
        cascade="all, delete-orphan",
    )
    results = relationship(
        "TournamentResult",
        back_populates="player",
        cascade="all, delete-orphan",
    )
    transactions = relationship(
        "WalletTransaction",
        back_populates="player",
        cascade="all, delete-orphan",
    )


class Tournament(Base):
    """Snooker tournament."""

    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    date = Column(DateTime, default=utc_now, nullable=False)
    type = Column(Enum(TournamentType), default=TournamentType.knockout, nullable=False)
    status = Column(
        Enum(TournamentStatus), default=TournamentStatus.PENDING, nullable=False
    )
    best_of = Column(Integer, default=3, nullable=False)
    race_to = Column(Integer, nullable=True)
    entry_fee = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    registrations = relationship(
        "TournamentRegistration",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    results = relationship(
        "TournamentResult",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )
    matches = relationship(
        "Match",
        back_populates="tournament",
        cascade="all, delete-orphan",
    )


class Match(Base):
    """Individual match inside a tournament."""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    score_player1 = Column(Integer, nullable=True)
    score_player2 = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    scheduled_at = Column(DateTime, default=utc_now, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("Player", foreign_keys=[player1_id])
    player2 = relationship("Player", foreign_keys=[player2_id])
    winner = relationship("Player", foreign_keys=[winner_id])


class TournamentRegistration(Base):
    """Link a player to a tournament entry."""

    __tablename__ = "tournament_registrations"
    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id", name="uq_registration"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    paid = Column(Boolean, default=False, nullable=False)
    waived = Column(Boolean, default=False, nullable=False)
    contribution = Column(Integer, default=0, nullable=False)

    tournament = relationship("Tournament", back_populates="registrations")
    player = relationship("Player", back_populates="registrations")


class TournamentResult(Base):
    """Leaderboard result for a tournament."""

    __tablename__ = "tournament_results"
    __table_args__ = (
        UniqueConstraint("tournament_id", "position", name="uq_tournament_position"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    tournament = relationship("Tournament", back_populates="results")
    player = relationship("Player", back_populates="results")


class WalletTransaction(Base):
    """Financial transaction linked to a player's wallet."""

    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=utc_now, nullable=False)

    player = relationship("Player", back_populates="transactions")


class User(Base):
    """Login identity; ownership is a unique server-controlled link."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('player', 'organiser', 'administrator')", name="user_role"
        ),
    )
    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(512), nullable=False)
    role = Column(String(20), nullable=False, default="player")
    is_active = Column(Boolean, nullable=False, default=True)
    player_id = Column(Integer, ForeignKey("players.id"), unique=True, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    session_id = Column(
        String(36), ForeignKey("auth_sessions.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, nullable=False, default=utc_now)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)


class TournamentOrganiser(Base):
    __tablename__ = "tournament_organisers"
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)


class AuthAuditEvent(Base):
    __tablename__ = "auth_audit_events"
    id = Column(Integer, primary_key=True)
    event = Column(String(64), nullable=False)
    success = Column(Boolean, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_id = Column(Integer, nullable=True)
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    bucket = Column(String(64), primary_key=True)
    attempts = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class FinancialWallet(Base):
    """New BWP wallet; never an inferred conversion of Player.balance."""

    __tablename__ = "financial_wallets"
    __table_args__ = (
        UniqueConstraint("id", "currency", name="uq_financial_wallet_currency"),
        CheckConstraint("currency = 'BWP'", name="currency_bwp"),
        CheckConstraint(
            "sequence > 0 OR balance_minor = 0", name="zero_opening_balance"
        ),
        CheckConstraint(
            "typeof(balance_minor) = 'integer' AND balance_minor BETWEEN 0 AND 9000000000000000",
            name="balance_minor_range",
        ),
        CheckConstraint(
            "typeof(sequence) = 'integer' AND sequence BETWEEN 0 AND 9000000000000000",
            name="sequence_range",
        ),
    )
    id = Column(String(36), primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), unique=True, nullable=False)
    currency = Column(String(3), nullable=False)
    balance_minor = Column(BigInteger, nullable=False, default=0)
    sequence = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class FinancialLedgerEntry(Base):
    """Append-only exact-money receipt, with globally unique retry identity."""

    __tablename__ = "financial_ledger_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["wallet_id", "currency"],
            ["financial_wallets.id", "financial_wallets.currency"],
        ),
        UniqueConstraint("wallet_id", "sequence", name="uq_financial_ledger_sequence"),
        CheckConstraint(
            "length(idempotency_key) = 36 AND substr(idempotency_key, 9, 1) = '-' AND substr(idempotency_key, 14, 1) = '-' AND substr(idempotency_key, 19, 1) = '-' AND substr(idempotency_key, 24, 1) = '-' AND substr(idempotency_key, 15, 1) = '4' AND substr(idempotency_key, 20, 1) IN ('8','9','a','b') AND length(replace(idempotency_key, '-', '')) = 32 AND replace(idempotency_key, '-', '') NOT GLOB '*[^0-9a-f]*'",
            name="idempotency_uuid4",
        ),
        CheckConstraint("currency = 'BWP'", name="currency_bwp"),
        CheckConstraint(
            "kind IN ('deposit', 'withdrawal', 'fee', 'prize')", name="posting_kind"
        ),
        CheckConstraint(
            "typeof(amount_minor) = 'integer' AND amount_minor BETWEEN 1 AND 9000000000000000",
            name="amount_minor_range",
        ),
        CheckConstraint(
            "typeof(balance_before_minor) = 'integer' AND balance_before_minor BETWEEN 0 AND 9000000000000000",
            name="balance_before_range",
        ),
        CheckConstraint(
            "typeof(balance_after_minor) = 'integer' AND balance_after_minor BETWEEN 0 AND 9000000000000000",
            name="balance_after_range",
        ),
        CheckConstraint(
            "typeof(sequence) = 'integer' AND sequence BETWEEN 1 AND 9000000000000000",
            name="sequence_range",
        ),
        CheckConstraint(
            "(kind IN ('deposit', 'prize') AND balance_after_minor = balance_before_minor + amount_minor) OR (kind IN ('withdrawal', 'fee') AND balance_after_minor = balance_before_minor - amount_minor)",
            name="posting_arithmetic",
        ),
    )
    id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(36), unique=True, nullable=False)
    wallet_id = Column(String(36), nullable=False)
    currency = Column(String(3), nullable=False)
    kind = Column(String(20), nullable=False)
    amount_minor = Column(BigInteger, nullable=False)
    balance_before_minor = Column(BigInteger, nullable=False)
    balance_after_minor = Column(BigInteger, nullable=False)
    sequence = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


from app.financial_schema import attach_ledger_triggers

attach_ledger_triggers(FinancialLedgerEntry.__table__)
