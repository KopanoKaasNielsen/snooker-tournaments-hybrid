from app.database import SessionLocal
from app.models import Player


def test_seeded_players_exist():
    db = SessionLocal()
    players = db.query(Player).all()
    assert len(players) >= 1, "Expected at least one seeded player"
    db.close()
