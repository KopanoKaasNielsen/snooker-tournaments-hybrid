from app.services import wallet
from app.models import Player
from app.database import SessionLocal


def test_wallet_flow():
    db = SessionLocal()
    player = Player(name="Wallet Test")
    db.add(player)
    db.commit()
    db.refresh(player)

    pid = player.id

    # Initial balance should be 0
    assert wallet.get_balance(db, pid) == 0.0

    # Deposit
    wallet.deposit(db, pid, 100.0)
    assert wallet.get_balance(db, pid) == 100.0

    # Withdraw
    wallet.withdraw(db, pid, 40.0)
    assert wallet.get_balance(db, pid) == 60.0

    # Overdraw (should raise)
    try:
        wallet.withdraw(db, pid, 100.0)
        assert False, "Expected overdraw to raise error"
    except ValueError as e:
        assert "Insufficient balance" in str(e)

    db.close()
