from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.schemas import TournamentRegistrationCreate
from app.services import wallet

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.post("/", response_model=schemas.Tournament)
def create_tournament(tournament: schemas.TournamentCreate, db: Session = Depends(get_db)):
    if isinstance(tournament.date, str):
        tournament.date = datetime.fromisoformat(tournament.date)
    return crud.create_tournament(db, tournament)


@router.get("/", response_model=List[schemas.Tournament])
def list_tournaments(db: Session = Depends(get_db)):
    return crud.get_tournaments(db)


@router.post("/{tournament_id}/register")
def register_player(
    tournament_id: int,
    registration: TournamentRegistrationCreate,
    db: Session = Depends(get_db),
):
    tournament = crud.get_tournament(db, tournament_id)
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found.")

    player = crud.get_player(db, registration.player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if tournament.entry_fee:
        try:
            wallet.withdraw(db, player.id, tournament.entry_fee)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return crud.register_player(db, tournament_id, registration.player_id)


@router.post('/{tournament_id}/complete', response_model=List[schemas.TournamentResult])
def complete_tournament(
    tournament_id: int,
    winners: List[schemas.WinnerCreate],
    db: Session = Depends(get_db),
):
    return crud.complete_tournament(db, tournament_id, winners)
