from sqlalchemy.orm import Session

from app.models import Player, TransactionType, WalletTransaction


def get_balance(db: Session, player_id: int) -> float:
    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")
    return player.balance


def deposit(db: Session, player_id: int, amount: float):
    if amount <= 0:
        raise ValueError("Deposit amount must be positive.")

    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")

    player.balance += amount
    db.add(WalletTransaction(player_id=player_id, type=TransactionType.deposit, amount=amount))
    db.commit()
    db.refresh(player)
    return player


def withdraw(db: Session, player_id: int, amount: float):
    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive.")

    player = db.query(Player).get(player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")

    if player.balance < amount:
        raise ValueError("Insufficient balance.")

    player.balance -= amount
    db.add(WalletTransaction(player_id=player_id, type=TransactionType.withdrawal, amount=amount))
    db.commit()
    db.refresh(player)
    return player
