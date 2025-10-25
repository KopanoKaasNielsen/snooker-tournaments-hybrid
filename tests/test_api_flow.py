import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from tests.conftest import TestingSessionLocal
from app.models import Tournament


@pytest.mark.asyncio
async def test_api_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Create players + deposit balance
        player_ids = []
        for name in ["Ronnie", "Selby"]:
            r = await client.post("/players/", json={"name": name})
            assert r.status_code == 200
            pid = r.json()["id"]
            player_ids.append(pid)
            await client.post(f"/players/{pid}/deposit", json={"amount": 100})

        # 2. Create tournament
        tournament_data = {
            "name": "API Cup",
            "type": "knockout",
            "date": "2025-11-01T12:00:00",
            "best_of": 5,
            "race_to": 3,
            "entry_fee": 50,
        }
        t = await client.post("/tournaments/", json=tournament_data)
        assert t.status_code == 200
        tid = t.json()["id"]

        # 3. Register both players
        for pid in player_ids:
            r = await client.post(f"/tournaments/{tid}/register", json={"player_id": pid})
            assert r.status_code == 200

        # 4. Generate matches (direct DB for now)
        db = TestingSessionLocal()
        tournament = db.query(Tournament).get(tid)
        from app.services.tournaments import generate_knockout_matches
        matches = generate_knockout_matches(db, tournament)
        assert len(matches) >= 1
        match = matches[0]
        match_id = match.id
        winner_id = match.player1_id
        db.expunge_all()
        db.close()

        # 5. Submit match result
        r = await client.post(
            f"/matches/{match_id}/result",
            json={"winner_id": winner_id, "score_player1": 3, "score_player2": 0},
        )
        assert r.status_code == 200
