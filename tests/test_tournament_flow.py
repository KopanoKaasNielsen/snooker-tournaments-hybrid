import pytest
from fastapi.testclient import TestClient
from app.main import app
import uuid


client = TestClient(app)
client = TestClient(app)

def unique_name(base: str) -> str:
    return f"{base}_{uuid.uuid4().hex[:6]}"



def test_full_tournament_flow():
    # Create players
    for i in range(1, 5):
        r = client.post("/players/", json={"name": f"Player {i}"})
        assert r.status_code == 200, f"Player creation failed: {r.text}"

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
    for pid in [1, 2, 3, 4]:
        r = client.post(
            f"/tournaments/{tournament_id}/register",
            json={"player_id": pid, "tournament_id": tournament_id},
        )
        assert r.status_code == 200, f"Failed to register player {pid}: {r.text}"


    # Complete tournament
    winners = [
        {"player_id": 1, "position": 1},
        {"player_id": 2, "position": 2},
        {"player_id": 3, "position": 3},
        {"player_id": 4, "position": 4},
    ]
    r = client.post(f"/tournaments/{tournament_id}/complete", json=winners)
    assert r.status_code == 200, f"Failed to complete tournament: {r.text}"


def test_register_same_player_twice():
    # Create player
    r = client.post("/players/", json={"name": "Player 1"})
    assert r.status_code == 200

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
        json={"player_id": 1, "tournament_id": tournament_id},
    )


    r1 = client.post(f"/tournaments/{tournament_id}/register", json={"player_id": 1, "tournament_id": tournament_id})
    assert r1.status_code == 200, f"First register failed: {r1.text}"

    r2 = client.post(f"/tournaments/{tournament_id}/register", json={"player_id": 1, "tournament_id": tournament_id})
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

    # Register valid players
    for pid in [1, 2]:
        client.post(f"/tournaments/{tournament_id}/register", json={"player_id": pid, "tournament_id": tournament_id})

    winners = [
        {"player_id": 1, "position": 1},
        {"player_id": 999, "position": 2},  # invalid player
    ]
    r = client.post(f"/tournaments/{tournament_id}/complete", json=winners)
    assert r.status_code == 400, f"Expected 400 but got {r.status_code}: {r.text}"

    # Create players and deposit balance
for i in range(1, 5):
    r = client.post("/players/", json={"name": f"Player {i}"})
    assert r.status_code == 200
    pid = r.json()["id"]
    # Deposit funds for entry
    client.post(f"/players/{pid}/deposit", json={"amount": 100})

