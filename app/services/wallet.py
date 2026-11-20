"""Legacy storage adapter; no currency inference or automatic BWP adoption.

HTTP mutations remain disabled. Decimal arithmetic and a fresh locked read repair
stale-session withdrawals; legacy Float storage is retained until approved adoption.
"""

from decimal import Context, Decimal, DecimalException, localcontext
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FinancialWallet, Player, TransactionType, WalletTransaction


def get_balance(db: Session, player_id: int) -> float:
    player = db.get(Player, player_id)
    if not player:
        raise ValueError(f"Player {player_id} not found.")
    return player.balance


def _post(db: Session, player_id: int, amount, *, withdrawal: bool):
    if isinstance(amount, bool) or not isinstance(amount, (Decimal, int, float)):
        raise ValueError("Amount must be a finite positive number")
    value = Decimal(str(amount))
    if not value.is_finite() or value <= 0:
        raise ValueError("Amount must be finite and positive")
    try:
        connection = db.connection()
        if connection.dialect.name == "sqlite":
            # SQLAlchemy autobegin on a SELECT need not start a sqlite3 transaction.
            # Take the writer reservation before refreshing any cached ORM balance.
            if not connection.connection.driver_connection.in_transaction:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
        statement = select(Player).where(Player.id == player_id)
        if connection.dialect.name != "sqlite":
            statement = statement.with_for_update()
        player = db.scalar(statement.execution_options(populate_existing=True))
        if not player:
            raise ValueError(f"Player {player_id} not found.")
        if db.scalar(
            select(FinancialWallet.id).where(FinancialWallet.player_id == player_id)
        ):
            raise ValueError(
                "Legacy writes cannot modify a player with an exact-money wallet"
            )
        balance = Decimal(str(player.balance))
        if not balance.is_finite() or balance < 0:
            raise ValueError("Legacy balance requires reconciliation")
        if withdrawal and balance < value:
            raise ValueError("Insufficient balance.")
        with localcontext(Context(prec=1000)) as context:
            context.prec = 1000
            result = balance - value if withdrawal else balance + value
        stored_balance, stored_amount = float(result), float(value)
        if not math.isfinite(stored_balance) or not math.isfinite(stored_amount):
            raise ValueError("Amount exceeds legacy storage range")
        # Storage compatibility only: no scale/currency is assigned or old row converted.
        player.balance = stored_balance
        db.add(
            WalletTransaction(
                player_id=player_id,
                type=(
                    TransactionType.withdrawal
                    if withdrawal
                    else TransactionType.deposit
                ),
                amount=stored_amount,
            )
        )
        db.commit()
        db.refresh(player)
        return player
    except DecimalException:
        db.rollback()
        raise ValueError("Invalid legacy arithmetic") from None
    except Exception:
        db.rollback()
        raise


def deposit(db: Session, player_id: int, amount: float):
    return _post(db, player_id, amount, withdrawal=False)


def withdraw(db: Session, player_id: int, amount: float):
    return _post(db, player_id, amount, withdrawal=True)
