from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy.exc import IntegrityError

from app.auth_config import get_auth_config
from app.main import app
from app.models import (
    Player,
    Tournament,
    TournamentOrganiser,
    TournamentRegistration,
    User,
    WalletTransaction,
)
from app.services import wallet
from tests.conftest import TestingSessionLocal


@pytest.fixture
def client():
    with TestClient(app) as result:
        yield result


@pytest.mark.parametrize("suffix", ["", "/balance", "/transactions", "/elo"])
def test_private_player_data_cannot_be_read_by_changing_id(
    client, account_factory, suffix
):
    owner, other, admin = (
        account_factory(),
        account_factory(),
        account_factory("administrator", linked=False),
    )
    path = f"/players/{owner['player_id']}{suffix}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=other["headers"]).status_code == 403
    assert client.get(path, headers=owner["headers"]).status_code == 200
    assert client.get(path, headers=admin["headers"]).status_code == 200


def test_player_listing_is_scoped_and_leaderboard_has_no_money(client, account_factory):
    owner, other = account_factory(), account_factory()
    records = client.get("/players/", headers=owner["headers"]).json()
    assert [p["id"] for p in records] == [owner["player_id"]]
    leaderboard = client.get("/players/leaderboard", headers=owner["headers"]).json()
    assert all("balance" not in item for item in leaderboard)


@pytest.mark.parametrize("role", ["player", "organiser", "administrator"])
@pytest.mark.parametrize("operation", ["deposit", "withdraw"])
def test_financial_mutations_disabled_for_every_role(
    client, account_factory, role, operation
):
    account = account_factory(role)
    with TestingSessionLocal() as db:
        db.get(Player, account["player_id"]).balance = 100
        db.commit()
    response = client.post(
        f"/players/{account['player_id']}/{operation}",
        json={"amount": 25},
        headers=account["headers"],
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FINANCIAL_OPERATIONS_DISABLED"
    with TestingSessionLocal() as db:
        assert db.get(Player, account["player_id"]).balance == 100
        assert db.query(WalletTransaction).count() == 0


def test_fee_registration_disabled_without_deducting_any_money(client, account_factory):
    player, admin = account_factory(), account_factory("administrator", linked=False)
    with TestingSessionLocal() as db:
        tournament = Tournament(name="Paid cup", entry_fee=25)
        db.add(tournament)
        db.flush()
        tid = tournament.id
        wallet.deposit(db, player["player_id"], 100)
    response = client.post(
        f"/tournaments/{tid}/register",
        json={"player_id": player["player_id"]},
        headers=admin["headers"],
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "FINANCIAL_OPERATIONS_DISABLED"
    with TestingSessionLocal() as db:
        assert db.get(Player, player["player_id"]).balance == 100
        assert db.query(WalletTransaction).count() == 1
        assert db.query(TournamentRegistration).count() == 0


def test_free_registration_owner_and_duplicate_checks(client, account_factory):
    player, other = account_factory(), account_factory()
    with TestingSessionLocal() as db:
        tournament = Tournament(name="Free cup", entry_fee=0)
        db.add(tournament)
        db.flush()
        tid = tournament.id
        db.commit()
    path = f"/tournaments/{tid}/register"
    assert (
        client.post(
            path, json={"player_id": player["player_id"]}, headers=other["headers"]
        ).status_code
        == 403
    )
    assert (
        client.post(
            path, json={"player_id": player["player_id"]}, headers=player["headers"]
        ).status_code
        == 200
    )
    assert (
        client.post(
            path, json={"player_id": player["player_id"]}, headers=player["headers"]
        ).status_code
        == 400
    )


def test_organiser_assignments_enforced_on_management_and_results(
    client, account_factory
):
    organiser, other, player = (
        account_factory("organiser"),
        account_factory("organiser"),
        account_factory(),
    )
    admin = account_factory("administrator", linked=False)
    payload = {"name": "Scoped cup", "type": "knockout", "entry_fee": 0}
    assert (
        client.post(
            "/tournaments/", json=payload, headers=player["headers"]
        ).status_code
        == 403
    )
    created = client.post("/tournaments/", json=payload, headers=organiser["headers"])
    assert created.status_code == 200
    tid = created.json()["id"]
    match_payload = {
        "tournament_id": tid,
        "player1_id": player["player_id"],
        "player2_id": other["player_id"],
    }
    assert (
        client.post(
            "/matches/", json=match_payload, headers=other["headers"]
        ).status_code
        == 403
    )
    match = client.post("/matches/", json=match_payload, headers=organiser["headers"])
    assert match.status_code == 200
    path = f"/matches/{match.json()['id']}/result"
    result = {"winner_id": player["player_id"], "score_player1": 3, "score_player2": 0}
    assert client.post(path, json=result, headers=other["headers"]).status_code == 403
    assert (
        client.put(
            f"/admin/tournaments/{tid}/organisers",
            json={"user_id": other["id"]},
            headers=admin["headers"],
        ).status_code
        == 204
    )
    assert client.post(path, json=result, headers=other["headers"]).status_code == 200
    assert (
        client.delete(
            f"/admin/tournaments/{tid}/organisers/{other['id']}",
            headers=admin["headers"],
        ).status_code
        == 204
    )
    assert client.post(path, json=result, headers=other["headers"]).status_code == 403


def test_admin_role_changes_revoke_sessions_and_client_roles_cannot_escalate(
    client, account_factory
):
    admin, player = account_factory("administrator", linked=False), account_factory()
    path = f"/admin/users/{player['id']}/role"
    assert (
        client.put(
            path, json={"role": "administrator"}, headers=player["headers"]
        ).status_code
        == 403
    )
    config = get_auth_config()
    claims = jwt.decode(
        player["token"],
        config.secret,
        algorithms=["HS256"],
        audience=config.audience,
        issuer=config.issuer,
    )
    claims["role"] = "administrator"
    forged_role = jwt.encode(claims, config.secret, algorithm="HS256")
    assert (
        client.get(
            "/admin/users", headers={"Authorization": "Bearer " + forged_role}
        ).status_code
        == 403
    )
    assert (
        client.put(
            path, json={"role": "organiser"}, headers=admin["headers"]
        ).status_code
        == 200
    )
    assert client.get("/auth/me", headers=player["headers"]).status_code == 401
    assert (
        client.get("/admin/audit-events", headers=admin["headers"]).status_code == 200
    )
    assert (
        client.get("/admin/audit-events", headers=player["headers"]).status_code == 401
    )


def test_last_admin_protection_and_admin_deactivation(client, account_factory):
    admin, player = account_factory("administrator", linked=False), account_factory()
    assert (
        client.post(
            f"/admin/users/{admin['id']}/deactivate", headers=admin["headers"]
        ).status_code
        == 409
    )
    assert (
        client.put(
            f"/admin/users/{admin['id']}/role",
            json={"role": "player"},
            headers=admin["headers"],
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/admin/users/{player['id']}/deactivate", headers=admin["headers"]
        ).status_code
        == 204
    )
    assert client.get("/auth/me", headers=player["headers"]).status_code == 401


def test_ownership_unique_constraint(account_factory):
    owner = account_factory()
    with TestingSessionLocal() as db:
        db.add(
            User(
                username="duplicate_owner",
                password_hash="invalid",
                role="player",
                player_id=owner["player_id"],
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize(
    "path",
    [
        "/players/",
        "/players/leaderboard",
        "/matches/",
        "/tournaments/",
        "/auth/me",
        "/admin/users",
    ],
)
def test_private_endpoints_reject_unauthenticated_requests(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
