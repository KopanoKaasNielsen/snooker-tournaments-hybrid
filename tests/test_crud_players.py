from app.crud import create_player, get_player
from app.schemas import PlayerCreate
from tests.conftest import TestingSessionLocal
from app.models import Player


def test_create_and_get_player():
    db = TestingSessionLocal()
    new_player = PlayerCreate(name="Test Player CRUD")
    created = create_player(db, new_player)
    assert isinstance(created, Player)
    fetched = get_player(db, created.id)
    assert fetched.id == created.id
    assert fetched.name == created.name
    db.close()
