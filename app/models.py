"""Database models for the snooker tournaments application."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    type = Column(Enum(TournamentType), default=TournamentType.knockout, nullable=False)
    status = Column(Enum(TournamentStatus), default=TournamentStatus.PENDING, nullable=False)
    best_of = Column(Integer, default=3, nullable=False)
    race_to = Column(Integer, nullable=True)
    entry_fee = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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
    scheduled_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    tournament = relationship("Tournament", back_populates="results")
    player = relationship("Player", back_populates="results")


class WalletTransaction(Base):
    """Financial transaction linked to a player's wallet."""

    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    player = relationship("Player", back_populates="transactions")


# Seed the default SQLite database eagerly so ad-hoc imports have data
# available. The import is wrapped in a ``try`` block to avoid crashing during
# certain deployment scenarios where the seed helpers might be absent.
try:  # pragma: no cover - defensive import guard
    from app.init_db import seed_data
except Exception:  # pragma: no cover - best-effort seeding
    pass
else:  # pragma: no cover - side-effect only
    seed_data()
