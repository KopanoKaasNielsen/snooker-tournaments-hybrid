from sqlalchemy.orm import Session
from app.models import Player


def get_balance(db: Session, player_id: int) -> float:
    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")
    return player.balance


def deposit(db: Session, player_id: int, amount: float):
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")

    player.balance += amount
    db.commit()
    return player.balance


def withdraw(db: Session, player_id: int, amount: float):
    if amount <= 0:
        raise ValueError("Amount must be positive.")

    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")

    if player.balance < amount:
        raise ValueError("Insufficient balance.")

    player.balance -= amount
    db.commit()
    return player.balance
