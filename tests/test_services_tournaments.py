from datetime import datetime
import pytest
from sqlalchemy.orm import Session
from app.models import Tournament, Player, TournamentRegistration
from tests.conftest import TestingSessionLocal
from app.services.tournaments import distribute_prizes, generate_knockout_matches


def create_dummy_tournament(db: Session, player_count=4) -> Tournament:
    tournament = Tournament(
        name="Knockout Test",
        type="knockout",
        date=datetime.fromisoformat("2025-10-01T12:00:00"),
        best_of=5,
        race_to=3,
        entry_fee=100,
    )
    db.add(tournament)
    db.commit()
    db.refresh(tournament)

    for i in range(player_count):
        p = Player(name=f"Player {i}")
        db.add(p)
        db.flush()
        db.add(TournamentRegistration(player_id=p.id, tournament_id=tournament.id))

    db.commit()
    db.refresh(tournament)
    return tournament


def test_generate_knockout_matches_even():
    db = TestingSessionLocal()
    tournament = create_dummy_tournament(db, player_count=4)
    matches = generate_knockout_matches(db, tournament)
    assert len(matches) == 2  # 4 players → 2 matches
    db.close()


def test_generate_knockout_matches_odd():
    db = TestingSessionLocal()
    tournament = create_dummy_tournament(db, player_count=5)
    matches = generate_knockout_matches(db, tournament)
    assert len(matches) == 3  # 2 matches + 1 bye
    bye_matches = [m for m in matches if m.player2_id is None]
    assert len(bye_matches) == 1
    db.close()


def test_distribute_prizes():
    db = TestingSessionLocal()
    tournament = create_dummy_tournament(db, player_count=3)
    db.refresh(tournament)

    # Assign final standings (1st, 2nd, 3rd)
    players = [reg.player_id for reg in tournament.registrations]
    tournament.final_standings = players[:3]
    db.commit()

    distribute_prizes(db, tournament, prize_split=(0.6, 0.3, 0.1))

    for i, pid in enumerate(players[:3]):
        p = db.query(Player).get(pid)
        expected = round(tournament.entry_fee * 3 * [0.6, 0.3, 0.1][i], 2)
        assert p.balance == expected

    db.close()
