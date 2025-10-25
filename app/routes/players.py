from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.services import wallet

router = APIRouter(prefix="/players", tags=["players"])


@router.post("/", response_model=schemas.Player)
def create_player(player: schemas.PlayerCreate, db: Session = Depends(get_db)):
    return crud.create_player(db, player)


@router.get("/", response_model=list[schemas.Player])
def list_players(db: Session = Depends(get_db)):
    return crud.get_players(db)


@router.get("/leaderboard", response_model=list[schemas.PlayerOut])
def get_leaderboard(db: Session = Depends(get_db)):
    players = db.query(models.Player).order_by(models.Player.elo.desc()).limit(10).all()
    return players


@router.get("/{player_id}", response_model=schemas.Player)
def get_player(player_id: int, db: Session = Depends(get_db)):
    return crud.get_player(db, player_id)


@router.post("/{player_id}/deposit", response_model=schemas.PlayerBalanceOut)
def deposit(player_id: int, payload: schemas.WalletAmount, db: Session = Depends(get_db)):
    try:
        player = wallet.deposit(db, player_id, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"player_id": player.id, "balance": player.balance}


@router.post("/{player_id}/withdraw", response_model=schemas.PlayerBalanceOut)
def withdraw(player_id: int, payload: schemas.WalletAmount, db: Session = Depends(get_db)):
    try:
        player = wallet.withdraw(db, player_id, payload.amount)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"player_id": player.id, "balance": player.balance}


@router.get("/{player_id}/balance", response_model=schemas.PlayerBalanceOut)
def get_player_balance(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player.id, "balance": player.balance}


@router.get("/{player_id}/elo", response_model=schemas.PlayerEloOut)
def get_player_elo(player_id: int, db: Session = Depends(get_db)):
    player = db.query(models.Player).get(player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"player_id": player.id, "elo": player.elo}


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
            "timestamp": t.timestamp.isoformat(),
        }
        for t in player.transactions
    ]
