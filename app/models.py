"""SQLAlchemy models for the snooker tournament service."""

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
)
from sqlalchemy.orm import relationship

from .database import Base


class TournamentType(enum.Enum):
    league = "league"
    knockout = "knockout"
    double_elimination = "double_elimination"


class TournamentStatus(enum.Enum):
    PENDING = "PENDING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TransactionType(enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"
    prize = "prize"
    fee = "fee"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    rating = Column(Integer, default=1500, nullable=False)
    elo = Column(Integer, default=1500, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    matches_as_player1 = relationship(
        "Match",
        back_populates="player1",
        foreign_keys="Match.player1_id",
    )
    matches_as_player2 = relationship(
        "Match",
        back_populates="player2",
        foreign_keys="Match.player2_id",
    )
    matches_won = relationship(
        "Match",
        back_populates="winner",
        foreign_keys="Match.winner_id",
    )
    transactions = relationship(
        "WalletTransaction",
        back_populates="player",
        cascade="all, delete-orphan",
    )


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(Enum(TournamentType), default=TournamentType.knockout, nullable=False)
    status = Column(Enum(TournamentStatus), default=TournamentStatus.PENDING, nullable=False)
    best_of = Column(Integer, default=3, nullable=False)
    race_to = Column(Integer, nullable=True)
    entry_fee = Column(Integer, default=0, nullable=False)

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

    def __init__(self, **kwargs):  # type: ignore[override]
        date_value = kwargs.get("date")
        if isinstance(date_value, str):
            try:
                kwargs["date"] = datetime.fromisoformat(date_value)
            except ValueError:
                kwargs["date"] = datetime.fromisoformat(date_value.replace("Z", ""))
        super().__init__(**kwargs)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player1_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    player2_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    score_player1 = Column(Integer, nullable=True)
    score_player2 = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey("players.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, default=datetime.utcnow)

    tournament = relationship("Tournament", back_populates="matches")
    player1 = relationship("Player", foreign_keys=[player1_id], back_populates="matches_as_player1")
    player2 = relationship("Player", foreign_keys=[player2_id], back_populates="matches_as_player2")
    winner = relationship("Player", foreign_keys=[winner_id], back_populates="matches_won")


class TournamentRegistration(Base):
    __tablename__ = "tournament_registrations"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    paid = Column(Boolean, default=False, nullable=False)
    waived = Column(Boolean, default=False, nullable=False)
    contribution = Column(Integer, default=0, nullable=False)

    tournament = relationship("Tournament", back_populates="registrations")
    player = relationship("Player", back_populates="registrations")


class TournamentResult(Base):
    __tablename__ = "tournament_results"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tournament = relationship("Tournament", back_populates="results")
    player = relationship("Player", back_populates="results")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", back_populates="transactions")
