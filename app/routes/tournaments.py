from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app import schemas, crud
from app.database import get_db

router = APIRouter(prefix='/tournaments', tags=['tournaments'])

@router.post('/', response_model=schemas.Tournament)
def create_tournament(tournament: schemas.TournamentCreate, db: Session = Depends(get_db)):
    return crud.create_tournament(db, tournament)

@router.get('/', response_model=List[schemas.Tournament])
def list_tournaments(db: Session = Depends(get_db)):
    return crud.get_tournaments(db)

@router.post('/{tournament_id}/register', response_model=schemas.TournamentRegistration)
def register_player(tournament_id: int, payload: schemas.TournamentRegistrationCreate, db: Session = Depends(get_db)):
    try:
        return crud.register_player(db, tournament_id, payload.player_id)
    except HTTPException as e:
        raise e

@router.post('/{tournament_id}/complete', response_model=List[schemas.TournamentResult])
def complete_tournament(tournament_id: int, winners: List[schemas.WinnerCreate], db: Session = Depends(get_db)):
    return crud.complete_tournament(db, tournament_id, winners)
