from app.services.matches import update_match_result
from app.models import Match, Player, Tournament
from app.database import SessionLocal


def test_update_match_result_and_elo():
    db = SessionLocal()

    t = Tournament(name="EloCup", type="knockout", date="2025-10-10T12:00:00", best_of=5, race_to=3)
    p1 = Player(name="Alice", elo=1500)
    p2 = Player(name="Bob", elo=1500)
    db.add_all([t, p1, p2])
    db.commit()
    db.refresh(t)
    db.refresh(p1)
    db.refresh(p2)

    match = Match(tournament_id=t.id, player1_id=p1.id, player2_id=p2.id)
    db.add(match)
    db.commit()
    db.refresh(match)

    updated = update_match_result(db, match.id, winner_id=p1.id)

    assert updated.winner_id == p1.id
    assert db.query(Player).get(p1.id).elo > 1500
    assert db.query(Player).get(p2.id).elo < 1500

    db.close()
