import pytest
from httpx import AsyncClient
from app.main import app
from app.database import SessionLocal
from app.models import Player, Tournament, TournamentRegistration


@pytest.mark.asyncio
async def test_api_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
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
        db = SessionLocal()
        tournament = db.query(Tournament).get(tid)
        from app.services.tournaments import generate_knockout_matches
        matches = generate_knockout_matches(db, tournament)
        db.close()

        assert len(matches) >= 1
        match = matches[0]

        # 5. Submit match result
        winner_id = match.player1_id
        r = await client.post(f"/matches/{match.id}/result", json={"winner_id": winner_id})
        assert r.status_code == 200
