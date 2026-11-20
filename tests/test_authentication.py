from datetime import timedelta, timezone

from argon2 import extract_parameters, Type
from fastapi.testclient import TestClient
import jwt
import pytest

from app.auth_config import get_auth_config
from app.main import app
from app.models import AuthAuditEvent, AuthSession, Player, RefreshToken, User
from app.security import hash_password, verify_password
from app.time import utc_now
from tests.conftest import TestingSessionLocal

PASSWORD = "Correct Horse Battery Staple!1"
WEB = {"X-Snooker-Client": "web"}


@pytest.fixture
def client():
    with TestClient(app, headers=WEB) as result:
        yield result


def login(client, account):
    response = client.post(
        "/auth/login",
        json={"username": account["username"], "password": account["password"]},
    )
    assert response.status_code == 200
    return response.json(), response


def test_argon2id_hashing_and_random_salts():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second and PASSWORD not in first
    parameters = extract_parameters(first)
    assert parameters.type == Type.ID
    assert parameters.memory_cost >= 65536 and parameters.time_cost >= 3
    assert verify_password(PASSWORD, first)
    assert not verify_password("wrong", first)
    assert not verify_password(PASSWORD, "invalid-hash")


def test_registration_creates_only_player_role_and_owned_new_record(client):
    response = client.post(
        "/auth/register", json={"username": " New_User ", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json()["username"] == "new_user"
    assert response.json()["role"] == "player"
    assert "password_hash" not in response.json()
    with TestingSessionLocal() as db:
        user = db.query(User).one()
        assert verify_password(PASSWORD, user.password_hash)
        assert db.get(Player, user.player_id).balance == 0
        assert db.query(AuthAuditEvent).one().event == "registration"


@pytest.mark.parametrize(
    "extra", [{"role": "administrator"}, {"player_id": 1}, {"is_active": True}]
)
def test_registration_rejects_role_and_ownership_claims(client, extra):
    response = client.post(
        "/auth/register", json={"username": "attacker", "password": PASSWORD, **extra}
    )
    assert response.status_code == 422
    with TestingSessionLocal() as db:
        assert db.query(User).count() == 0


def test_registration_never_claims_existing_player_by_name(client):
    with TestingSessionLocal() as db:
        db.add(Player(name="Legacy", balance=85.5))
        db.commit()
    response = client.post(
        "/auth/register",
        json={"username": "new_user", "password": PASSWORD, "player_name": "Legacy"},
    )
    assert response.status_code == 409
    with TestingSessionLocal() as db:
        assert db.query(User).count() == 0
        assert db.query(Player).one().balance == 85.5


def test_registration_can_leave_account_unlinked_for_review(client):
    response = client.post(
        "/auth/register",
        json={"username": "unlinked", "password": PASSWORD, "create_player": False},
    )
    assert response.status_code == 201 and response.json()["player_id"] is None
    with TestingSessionLocal() as db:
        assert db.query(Player).count() == 0


def test_login_me_cookie_and_only_hash_storage(client, account_factory):
    account = account_factory()
    data, response = login(client, account)
    assert data["expires_in"] == 300 and data["token_type"] == "bearer"
    assert data["user"]["id"] == account["id"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert response.headers["cache-control"] == "no-store"
    raw = client.cookies.get(get_auth_config().cookie_name)
    with TestingSessionLocal() as db:
        assert all(
            row.token_hash != raw and len(row.token_hash) == 64
            for row in db.query(RefreshToken)
        )
        assert PASSWORD not in str([event.reason for event in db.query(AuthAuditEvent)])
    me = client.get(
        "/auth/me", headers={"Authorization": "Bearer " + data["access_token"]}
    )
    assert me.status_code == 200 and me.json()["username"] == account["username"]


def test_failed_login_is_generic_for_unknown_and_wrong_password(
    client, account_factory
):
    account = account_factory()
    known = client.post(
        "/auth/login", json={"username": account["username"], "password": "wrong"}
    )
    unknown = client.post(
        "/auth/login", json={"username": "unknown", "password": "wrong"}
    )
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()
    with TestingSessionLocal() as db:
        assert (
            db.query(AuthAuditEvent).filter_by(event="login", success=False).count()
            == 2
        )


def test_refresh_rotation_and_replay_revoke_session_family(client, account_factory):
    account = account_factory()
    data, _ = login(client, account)
    old = client.cookies.get(get_auth_config().cookie_name)
    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    assert client.cookies.get(get_auth_config().cookie_name) != old
    replay = client.post(
        "/auth/refresh", headers={"Cookie": f"{get_auth_config().cookie_name}={old}"}
    )
    assert replay.status_code == 401
    assert (
        client.get(
            "/auth/me",
            headers={"Authorization": "Bearer " + refreshed.json()["access_token"]},
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer " + data["access_token"]}
        ).status_code
        == 401
    )
    with TestingSessionLocal() as db:
        assert db.query(AuthAuditEvent).filter_by(event="refresh_replay").count() == 1


def test_logout_revokes_access_and_refresh_immediately(client, account_factory):
    data, _ = login(client, account_factory())
    assert client.post("/auth/logout").status_code == 204
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer " + data["access_token"]}
        ).status_code
        == 401
    )
    assert client.post("/auth/refresh").status_code == 401
    assert client.cookies.get(get_auth_config().cookie_name) is None


@pytest.mark.parametrize(
    "change", ["expired", "issuer", "audience", "signature", "algorithm"]
)
def test_access_token_validation(client, account_factory, change):
    account = account_factory()
    config = get_auth_config()
    claims = jwt.decode(
        account["token"],
        config.secret,
        algorithms=["HS256"],
        audience=config.audience,
        issuer=config.issuer,
    )
    key, algorithm = config.secret, "HS256"
    if change == "expired":
        claims["exp"] = int(
            (utc_now() - timedelta(seconds=1)).replace(tzinfo=timezone.utc).timestamp()
        )
    if change == "issuer":
        claims["iss"] = "other"
    if change == "audience":
        claims["aud"] = "other"
    if change == "signature":
        key = "different-long-key-for-tests-only-" * 3
    if change == "algorithm":
        key, algorithm = "", "none"
    encoded = jwt.encode(claims, key, algorithm=algorithm)
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer " + encoded}
        ).status_code
        == 401
    )


def test_refresh_expiry(client, account_factory):
    data, _ = login(client, account_factory())
    with TestingSessionLocal() as db:
        db.query(AuthSession).update({"expires_at": utc_now() - timedelta(seconds=1)})
        db.commit()
    assert client.post("/auth/refresh").status_code == 401
    assert (
        client.get(
            "/auth/me", headers={"Authorization": "Bearer " + data["access_token"]}
        ).status_code
        == 401
    )


def test_deactivation_revokes_every_session_and_prevents_login(client, account_factory):
    account = account_factory()
    data, _ = login(client, account)
    headers = {"Authorization": "Bearer " + data["access_token"]}
    assert client.post("/auth/me/deactivate", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=account["headers"]).status_code == 401
    assert client.post("/auth/refresh").status_code == 401
    assert (
        client.post(
            "/auth/login", json={"username": account["username"], "password": PASSWORD}
        ).status_code
        == 401
    )


def test_auth_origin_and_custom_header_enforced(client):
    payload = {"username": "unknown", "password": "bad"}
    with TestClient(app) as plain:
        assert plain.post("/auth/login", json=payload).status_code == 403
    assert (
        client.post(
            "/auth/login", json=payload, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/auth/refresh", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )


def test_rate_limit_is_enforced_before_unbounded_password_work(client):
    for _ in range(10):
        assert (
            client.post(
                "/auth/login", json={"username": "unknown", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login", json={"username": "unknown", "password": "bad"}
        ).status_code
        == 429
    )


def test_password_validation_never_echoes_secret(client):
    response = client.post(
        "/auth/register", json={"username": "new_user", "password": "short-secret"}
    )
    assert response.status_code == 422 and "short-secret" not in response.text


def test_production_requires_secret_and_https(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_SECRET_KEY"):
        with TestClient(app):
            pass
    monkeypatch.setenv("AUTH_SECRET_KEY", "placeholder")
    with pytest.raises(RuntimeError):
        get_auth_config()
    monkeypatch.setenv("AUTH_SECRET_KEY", "valid-test-key-for-configuration-only-" * 3)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://127.0.0.1:5173")
    with pytest.raises(RuntimeError, match="HTTPS"):
        get_auth_config()


def test_production_cookie_is_secure_and_host_only(
    client, account_factory, monkeypatch
):
    account = account_factory()
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "https://game.example")
    with TestClient(app, base_url="https://testserver", headers=WEB) as secure:
        _, response = login(secure, account)
        cookie = response.headers["set-cookie"]
        assert (
            "__Host-snooker_refresh=" in cookie
            and "Secure" in cookie
            and "Domain=" not in cookie
        )
