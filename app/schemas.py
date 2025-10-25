from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PlayerBase(BaseModel):
    name: str
    rating: Optional[int] = 1500

class PlayerCreate(PlayerBase):
    rating: int = 1500

class Player(PlayerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class TournamentBase(BaseModel):
    name: str
    type: str = Field(..., description='league|knockout|double_elimination')
    date: Optional[datetime] = None
    entry_fee: Optional[int] = 0
    best_of: Optional[int] = 3
    race_to: Optional[int] = None

class TournamentCreate(TournamentBase):
    pass

class Tournament(TournamentBase):
    id: int
    status: str

    class Config:
        from_attributes = True

class TournamentRegistrationBase(BaseModel):
    player_id: int

    id: int
    tournament_id: int

    class Config:
        from_attributes = True

class WinnerCreate(BaseModel):
    player_id: int = Field(...)
    position: int = Field(..., ge=1, le=4)

class PlayerInTournament(BaseModel):
    player_id: int
    name: str
    tournament_id: Optional[int] = None
    id: Optional[int] = None

    class Config:
        from_attributes = True

class TournamentResult(BaseModel):
    id: int
    tournament_id: int
    player_id: int
    position: int
    created_at: datetime

    class Config:
        from_attributes = True

################
class MatchBase(BaseModel):
    tournament_id: int
    player1_id: int
    player2_id: int
    scheduled_at: Optional[datetime] = None


class MatchCreate(BaseModel):
    tournament_id: int
    player1_id: int
    player2_id: int
    scheduled_at: Optional[datetime] = None


class MatchResult(BaseModel):
    """Used to report the result of a match."""
    score_player1: Optional[int] = None
    score_player2: Optional[int] = None
    winner_id: int


class Match(MatchBase):
    id: int
    score_player1: Optional[int] = 0
    score_player2: Optional[int] = 0
    winner_id: Optional[int] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TournamentRegistrationCreate(BaseModel):
    player_id: int


class PlayerBalanceOut(BaseModel):
    player_id: int
    balance: float

class PlayerEloOut(BaseModel):
    player_id: int
    elo: int

class WalletTransactionOut(BaseModel):
    id: int
    type: str
    amount: float
    timestamp: str
