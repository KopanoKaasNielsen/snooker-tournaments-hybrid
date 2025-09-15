from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_balance_and_elo_endpoints():
    # Create player
    r = client.post("/players/", json={"name": "StatMan"})
    assert r.status_code == 200
    pid = r.json()["id"]

    # Deposit to wallet
    r = client.post(f"/players/{pid}/deposit", json={"amount": 150})
    assert r.status_code == 200

    # Get balance
    r = client.get(f"/players/{pid}/balance")
    assert r.status_code == 200
    assert r.json()["balance"] == 150

    # Get Elo
    r = client.get(f"/players/{pid}/elo")
    assert r.status_code == 200
    assert r.json()["elo"] == 1500
