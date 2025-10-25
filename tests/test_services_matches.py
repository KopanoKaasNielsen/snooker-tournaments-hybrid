from datetime import datetime
from tests.conftest import TestingSessionLocal
from app.models import Match, Player, Tournament
from app.services.matches import update_match_result


def test_update_match_result_and_elo():
    db = TestingSessionLocal()
    try:
        db.query(Match).delete()
        db.query(Tournament).delete()
        db.query(Player).delete()
        db.commit()

        tournament = Tournament(
            name="EloCup",
            type="knockout",
            date=datetime.fromisoformat("2025-10-10T12:00:00"),
            best_of=5,
            race_to=3,
        )
        player_one = Player(name="Alice", elo=1500)
        player_two = Player(name="Bob", elo=1500)
        db.add_all([tournament, player_one, player_two])
        db.commit()
        db.refresh(tournament)
        db.refresh(player_one)
        db.refresh(player_two)

        match = Match(tournament_id=tournament.id, player1_id=player_one.id, player2_id=player_two.id)
        db.add(match)
        db.commit()
        db.refresh(match)

        updated = update_match_result(db, match.id, winner_id=player_one.id)

        assert updated.winner_id == player_one.id
        assert db.query(Player).get(player_one.id).elo > 1500
        assert db.query(Player).get(player_two.id).elo < 1500
    finally:
        db.close()
