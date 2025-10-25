from fastapi.testclient import TestClient
from app.main import app
import uuid


client = TestClient(app)


def unique_name(base: str) -> str:
    return f"{base}_{uuid.uuid4().hex[:6]}"


def create_players_with_balance(count: int, deposit_amount: float = 100.0) -> list[int]:
    player_ids: list[int] = []
    for i in range(1, count + 1):
        response = client.post("/players/", json={"name": unique_name(f"Player {i}")})
        assert response.status_code == 200, f"Player creation failed: {response.text}"
        pid = response.json()["id"]
        deposit = client.post(f"/players/{pid}/deposit", json={"amount": deposit_amount})
        assert deposit.status_code == 200, f"Deposit failed for player {pid}: {deposit.text}"
        player_ids.append(pid)
    return player_ids


def test_full_tournament_flow():
    player_ids = create_players_with_balance(4)

    tournament_data = {
        "name": unique_name("Test Open Flow"),
        "type": "knockout",
        "date": "2025-09-15T12:00:00",
        "best_of": 5,
        "race_to": 3,
        "entry_fee": 50,
    }
    response = client.post("/tournaments/", json=tournament_data)
    assert response.status_code == 200, f"Unexpected response: {response.text}"
    tournament = response.json()
    tournament_id = tournament["id"]

    # Register players
    for pid in player_ids:
        r = client.post(
            f"/tournaments/{tournament_id}/register",
            json={"player_id": pid, "tournament_id": tournament_id},
        )
        assert r.status_code == 200, f"Failed to register player {pid}: {r.text}"


    # Complete tournament
    winners = [
        {"player_id": pid, "position": index + 1}
        for index, pid in enumerate(player_ids)
    ]
    r = client.post(f"/tournaments/{tournament_id}/complete", json=winners)
    assert r.status_code == 200, f"Failed to complete tournament: {r.text}"


def test_register_same_player_twice():
    player_id = create_players_with_balance(1)[0]

    # Create tournament
    tournament_data = {
        "name": unique_name("Duplicate Test"),
        "type": "knockout",
        "date": "2025-09-16T12:00:00",
        "best_of": 5,
        "race_to": 3,
        "entry_fee": 50,
    }
    
    response = client.post("/tournaments/", json=tournament_data)
    assert response.status_code == 200, f"Unexpected response: {response.text}"
    tournament_id = response.json()["id"]




# Register player twice
    r1 = client.post(
        f"/tournaments/{tournament_id}/register",
        json={"player_id": player_id, "tournament_id": tournament_id},
    )
    assert r1.status_code == 200, f"First register failed: {r1.text}"

    r2 = client.post(
        f"/tournaments/{tournament_id}/register",
        json={"player_id": player_id, "tournament_id": tournament_id},
    )
    assert r2.status_code == 400, f"Expected 400 duplicate error but got {r2.status_code}: {r2.text}"


def test_complete_tournament_with_invalid_player():
    tournament_data = {
        "name": unique_name("Invalid Winners Test"),
        "type": "knockout",
        "date": "2025-09-17T12:00:00",
        "best_of": 5,
        "race_to": 3,
        "entry_fee": 50,
    }
    response = client.post("/tournaments/", json=tournament_data)
    assert response.status_code == 200, f"Unexpected response: {response.text}"
    tournament_id = response.json()["id"]

    player_ids = create_players_with_balance(2)

    # Register valid players
    for pid in player_ids:
        reg_resp = client.post(
            f"/tournaments/{tournament_id}/register",
            json={"player_id": pid, "tournament_id": tournament_id},
        )
        assert reg_resp.status_code == 200, f"Failed to register player {pid}: {reg_resp.text}"

    winners = [
        {"player_id": player_ids[0], "position": 1},
        {"player_id": 999, "position": 2},  # invalid player
    ]
    r = client.post(f"/tournaments/{tournament_id}/complete", json=winners)
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}: {r.text}"

