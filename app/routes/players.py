from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.security import (
    current_user,
    financial_disabled,
    player_permission,
    require_admin,
)

router = APIRouter(prefix="/players", tags=["players"])


@router.post("/", response_model=schemas.Player)
def create_player(
    player: schemas.PlayerCreate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crud.create_player(db, player)


@router.get("/", response_model=list[schemas.Player])
def list_players(
    user: models.User = Depends(current_user), db: Session = Depends(get_db)
):
    if user.role == "administrator":
        return crud.get_players(db)
    return db.query(models.Player).filter(models.Player.id == user.player_id).all()


@router.get("/leaderboard", response_model=list[schemas.PublicLeaderboardPlayer])
def get_leaderboard(
    user: models.User = Depends(current_user), db: Session = Depends(get_db)
):
    # Public competition fields only; the old PlayerOut included private balances.
    return db.query(models.Player).order_by(models.Player.elo.desc()).limit(10).all()


@router.get("/{player_id}", response_model=schemas.Player)
def get_player(
    player_id: int,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    player_permission(user, player_id)
    return crud.get_player(db, player_id)


@router.post("/{player_id}/deposit", response_model=schemas.PlayerBalanceOut)
def deposit(
    player_id: int,
    payload: schemas.WalletAmount,
    user: models.User = Depends(current_user),
):
    player_permission(user, player_id)
    financial_disabled()


@router.post("/{player_id}/withdraw", response_model=schemas.PlayerBalanceOut)
def withdraw(
    player_id: int,
    payload: schemas.WalletAmount,
    user: models.User = Depends(current_user),
):
    player_permission(user, player_id)
    financial_disabled()


@router.get("/{player_id}/balance", response_model=schemas.PlayerBalanceOut)
def get_player_balance(
    player_id: int,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    player_permission(user, player_id)
    player = crud.get_player(db, player_id)
    return {"player_id": player.id, "balance": player.balance}


@router.get("/{player_id}/elo", response_model=schemas.PlayerEloOut)
def get_player_elo(
    player_id: int,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    player_permission(user, player_id)
    player = crud.get_player(db, player_id)
    return {"player_id": player.id, "elo": player.elo}


@router.get(
    "/{player_id}/transactions", response_model=list[schemas.WalletTransactionOut]
)
def get_wallet_transactions(
    player_id: int,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    player_permission(user, player_id)
    player = crud.get_player(db, player_id)
    return [
        {
            "id": t.id,
            "type": t.type,
            "amount": t.amount,
            "timestamp": t.timestamp.isoformat(),
        }
        for t in player.transactions
    ]
