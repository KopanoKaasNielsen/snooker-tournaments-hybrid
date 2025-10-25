"""Wallet related helpers."""

from sqlalchemy.orm import Session

from app.models import Player, TransactionType, WalletTransaction


def _get_player(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")
    return player


def get_balance(db: Session, player_id: int) -> float:
    return _get_player(db, player_id).balance


def deposit(db: Session, player_id: int, amount: float) -> float:
    if amount <= 0:
        raise ValueError("Deposit amount must be positive.")

    player = _get_player(db, player_id)
    player.balance += float(amount)

    db.add(
        WalletTransaction(
            player_id=player_id,
            type=TransactionType.deposit,
            amount=float(amount),
        )
    )
    db.commit()
    db.refresh(player)
    return player.balance


def withdraw(db: Session, player_id: int, amount: float) -> float:
    if amount <= 0:
        raise ValueError("Withdrawal amount must be positive.")

    player = _get_player(db, player_id)
    if player.balance < amount:
        raise ValueError("Insufficient balance.")

    player.balance -= float(amount)
    db.add(
        WalletTransaction(
            player_id=player_id,
            type=TransactionType.withdrawal,
            amount=float(amount),
        )
    )
    db.commit()
    db.refresh(player)
    return player.balance
