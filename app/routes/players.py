from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import schemas, crud
from app.database import get_db
########
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, models

router = APIRouter()

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
############################################
@router.get("/{player_id}/balance", response_model=__import__('app.schemas',fromlist=['']).schemas.PlayerBalanceOut)
def get_player_balance(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player.id, "balance": player.balance}


@router.get("/{player_id}/elo", response_model=__import__('app.schemas',fromlist=['']).schemas.PlayerEloOut)
def get_player_elo(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player.id, "elo": player.elo}

@router.get("/leaderboard")
def get_leaderboard(limit: int = 10, db: Session = Depends(get_db)):
    players = (
        db.query(models.Player)
        .order_by(models.Player.elo.desc())
        .limit(limit)
        .all()
    )
    return [
        {"player_id": p.id, "name": p.name, "elo": p.elo, "balance": p.balance}
        for p in players
    ]
@router.get("/{player_id}/transactions")
def get_wallet_transactions(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return [
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "timestamp": t.timestamp.isoformat()
        }
        for t in player.transactions
    ]
