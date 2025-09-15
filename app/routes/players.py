from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import schemas, crud
from app.database import get_db

router = APIRouter(prefix='/players', tags=['players'])

@router.post('/', response_model=schemas.Player)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    return crud.create_player(db, player)

@router.get('/', response_model=list[schemas.Player])
def list_players(db: Session = Depends(get_db)):
    return crud.get_players(db)

@router.get('/{player_id}', response_model=schemas.Player)
def get_player(player_id: int, db: Session = Depends(get_db)):
    return crud.get_player(db, player_id)
