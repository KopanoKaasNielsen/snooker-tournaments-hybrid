from app.init_db import DEFAULT_PLAYERS, seed_data
from app.models import Player
from tests.conftest import TestingSessionLocal


def test_seeded_players_exist():
    seed_data(TestingSessionLocal)
    with TestingSessionLocal() as db:
        names = {player.name for player in db.query(Player).all()}
        assert set(DEFAULT_PLAYERS) <= names
