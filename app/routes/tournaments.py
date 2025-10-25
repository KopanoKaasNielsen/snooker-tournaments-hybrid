"""Tournament API routes."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.post("/", response_model=schemas.Tournament)
def create_tournament(tournament: schemas.TournamentCreate, db: Session = Depends(get_db)):
    return crud.create_tournament(db, tournament)


@router.get("/", response_model=List[schemas.Tournament])
def list_tournaments(db: Session = Depends(get_db)):
    return crud.get_tournaments(db)


@router.post("/{tournament_id}/register")
def register_player(
    tournament_id: int,
    registration: schemas.TournamentRegistrationCreate,
    db: Session = Depends(get_db),
):
    return crud.register_player(db, tournament_id, registration.player_id)


@router.post("/{tournament_id}/complete", response_model=List[schemas.TournamentResult])
def complete_tournament(
    tournament_id: int,
    winners: List[schemas.WinnerCreate],
    db: Session = Depends(get_db),
):
    return crud.complete_tournament(db, tournament_id, winners)
