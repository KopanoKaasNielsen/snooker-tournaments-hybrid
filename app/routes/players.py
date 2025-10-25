"""Player related API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.services import wallet


class _AmountRequest(BaseModel):
    amount: float


router = APIRouter(prefix="/players", tags=["players"])


@router.post("/", response_model=schemas.Player)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    return crud.create_player(db, player)


@router.get("/", response_model=list[schemas.Player])
def list_players(db: Session = Depends(get_db)):
    return crud.get_players(db)


@router.get("/{player_id}/balance", response_model=schemas.PlayerBalanceOut)
def get_player_balance(player_id: int, db: Session = Depends(get_db)):
    player = db.get(models.Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player.id, "balance": player.balance}


@router.post("/{player_id}/deposit", response_model=schemas.PlayerBalanceOut)
def deposit(player_id: int, payload: _AmountRequest, db: Session = Depends(get_db)):
    try:
        balance = wallet.deposit(db, player_id, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"player_id": player_id, "balance": balance}


@router.post("/{player_id}/withdraw", response_model=schemas.PlayerBalanceOut)
def withdraw(player_id: int, payload: _AmountRequest, db: Session = Depends(get_db)):
    try:
        balance = wallet.withdraw(db, player_id, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"player_id": player_id, "balance": balance}


@router.get("/{player_id}/elo", response_model=schemas.PlayerEloOut)
def get_player_elo(player_id: int, db: Session = Depends(get_db)):
    player = db.get(models.Player, player_id)
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
    player = db.get(models.Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return [
        {
            "id": t.id,
            "type": t.type.value,
            "amount": t.amount,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in player.transactions
    ]


@router.get("/{player_id}", response_model=schemas.Player)
def get_player(player_id: int, db: Session = Depends(get_db)):
    return crud.get_player(db, player_id)
