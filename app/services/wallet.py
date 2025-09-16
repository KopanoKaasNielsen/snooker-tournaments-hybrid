from sqlalchemy.orm import Session
from app.models import Player
from app.models import WalletTransaction, TransactionType


def get_balance(db: Session, player_id: int) -> float:
    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")
    return player.balance


def deposit(db: Session, player_id: int, amount: float):
    ...
    db.add(WalletTransaction(player_id=player_id, type=TransactionType.deposit, amount=amount))
    db.commit()
    return Player.balance


def withdraw(db: Session, player_id: int, amount: float):
    ...
    db.add(WalletTransaction(player_id=player_id, type=TransactionType.withdrawal, amount=amount))
    db.commit()
    return Player.balance

