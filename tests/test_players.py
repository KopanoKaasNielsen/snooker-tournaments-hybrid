from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Player

client = TestClient(app)

def test_wallet_transaction_history():
    r = client.post("/players/", json={"name": "LogTest"})
    pid = r.json()["id"]

    client.post(f"/players/{pid}/deposit", json={"amount": 100})
    client.post(f"/players/{pid}/deposit", json={"amount": 50})
    client.post(f"/players/{pid}/withdraw", json={"amount": 30})

    r = client.get(f"/players/{pid}/transactions")
    data = r.json()
    assert len(data) == 3
    assert data[0]["type"] == "deposit"
    assert data[-1]["type"] == "withdrawal"



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

def test_leaderboard_endpoint():
    db = SessionLocal()
    # Create players with Elo directly set
    players = []
    for name, elo in [("Alice", 1800), ("Bob", 1500), ("Carl", 1700)]:
        p = Player(name=name, elo=elo)
        db.add(p)
        db.flush()
        players.append(p)
    db.commit()
    db.close()

    # Call leaderboard endpoint
    r = client.get("/players/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 3
    assert data[0]["elo"] >= data[1]["elo"] >= data[2]["elo"]