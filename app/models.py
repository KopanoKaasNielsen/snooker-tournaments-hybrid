

import enum
from datetime import datetime
from sqlalchemy import Float, Column, Integer, String, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy import Float, Enum as PgEnum
from sqlalchemy import Float, Column, Integer, String, ForeignKey, DateTime, Enum, Float
from sqlalchemy import MetaData
from .database import Base

# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Enum as SAEnum, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum

class TournamentType(enum.Enum):
    league = "league"
    knockout = "knockout"
    double_elimination = "double_elimination"

class TournamentStatus(enum.Enum):
    PENDING = "PENDING"
    ONGOING = "ONGOING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    rating = Column(Integer, default=1500)
    created_at = Column(DateTime, default=datetime.utcnow)

    registrations = relationship('TournamentRegistration', back_populates='player')
    results = relationship('TournamentResult', back_populates='player')
    transactions = relationship("WalletTransaction", back_populates="player", cascade="all, delete-orphan")

class Tournament(Base):
    __tablename__ = "tournaments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    type = Column(Enum(TournamentType), default=TournamentType.knockout)
    status = Column(Enum(TournamentStatus), default=TournamentStatus.PENDING)
    best_of = Column(Integer, default=3)
    race_to = Column(Integer, nullable=True)
    entry_fee = Column(Integer, default=0)

    registrations = relationship('TournamentRegistration', back_populates='tournament')
    results = relationship('TournamentResult', back_populates='tournament')
    matches = relationship('Match', back_populates='tournament')

class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'))
    player1_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    player2_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    score_player1 = Column(Integer, nullable=True)
    score_player2 = Column(Integer, nullable=True)
    winner_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    tournament = relationship('Tournament', back_populates='matches')
    player1 = relationship('Player', foreign_keys=[player1_id])
    player2 = relationship('Player', foreign_keys=[player2_id])
    winner = relationship('Player', foreign_keys=[winner_id])

    scheduled_at = Column(DateTime, default=datetime.utcnow)



class TournamentRegistration(Base):
    __tablename__ = "tournament_registrations"
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'))
    player_id = Column(Integer, ForeignKey('players.id'))
    paid = Column(Boolean, default=False)
    waived = Column(Boolean, default=False)
    contribution = Column(Integer, default=0)

    tournament = relationship('Tournament', back_populates='registrations')
    player = relationship('Player', back_populates='registrations')

class TournamentResult(Base):
    __tablename__ = "tournament_results"
    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id'))
    player_id = Column(Integer, ForeignKey('players.id'))
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    tournament = relationship('Tournament', back_populates='results')
    player = relationship('Player', back_populates='results')



class TransactionType(str, enum.Enum):
    deposit = "deposit"
    withdrawal = "withdrawal"

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    type = Column(PgEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    player = relationship("Player", back_populates="transactions")
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
    Boolean,
    Float,
)
from sqlalchemy import Enum as PgEnum
from sqlalchemy.orm import relationship

from .database import Base


class PlayerStatus(str, enum.Enum):
    active = "active"
    banned = "banned"


class WalletStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class TransactionType(enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    PRIZE = "prize"
    FEE = "fee"


class Player(Base):
    __tablename__ = "players"
    
    # ... your other columns ...

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(PgEnum(PlayerStatus), default=PlayerStatus.active, nullable=False)

    wallet = relationship("Wallet", back_populates="player", uselist=False)
    transactions = relationship("WalletTransaction", back_populates="player")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    balance = Column(Float, default=0.0)
    status = Column(PgEnum(WalletStatus), default=WalletStatus.active, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player = relationship("Player", back_populates="wallet")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    type = Column(SAEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)  # <-- correct SQLAlchemy type
    timestamp = Column(DateTime, default=datetime.utcnow)
    player = relationship("Player", back_populates="transactions")

Base.metadata.clear()





