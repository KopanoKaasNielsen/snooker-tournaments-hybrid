import os
import sys
import tempfile
import secrets

# Existing tests import tests.conftest directly; share the same fixture engine.
sys.modules.setdefault("tests.conftest", sys.modules[__name__])

# Isolate all application connections before imports; no implicit demo seeding.
_test_directory = tempfile.TemporaryDirectory(prefix="snooker-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_directory.name}/seed.db"

os.environ["AUTH_SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["APP_ENV"] = "development"
os.environ["AUTH_COOKIE_SECURE"] = "false"

import pytest
from sqlalchemy.orm import sessionmaker

from app import models  # ensure models are registered
from app.database import Base, get_db, make_engine
from app.main import app

TEST_SQLITE_URL = f"sqlite:///{_test_directory.name}/test.db"
engine = make_engine(TEST_SQLITE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True, scope="function")
def fresh_database():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def override_get_db():
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def account_factory():
    """Real DB users/sessions for permission tests, never a dependency bypass."""
    import uuid
    from functools import lru_cache
    from app.models import User, Player
    from app.security import create_session, hash_password

    def create(
        role="player",
        *,
        linked=True,
        username=None,
        password="Correct Horse Battery Staple!1",
    ):
        name = username or "user_" + uuid.uuid4().hex[:12]
        with TestingSessionLocal() as db:
            player = Player(name=name) if linked else None
            if player:
                db.add(player)
                db.flush()
            user = User(
                username=name,
                password_hash=hash_password(password),
                role=role,
                player_id=player.id if player else None,
            )
            db.add(user)
            db.flush()
            token, refresh = create_session(db, user)
            result = {
                "id": user.id,
                "username": name,
                "player_id": user.player_id,
                "password": password,
                "token": token,
                "refresh": refresh,
                "headers": {"Authorization": "Bearer " + token},
            }
            db.commit()
            return result

    return create


@pytest.fixture
def admin_headers(account_factory):
    return account_factory("administrator", linked=False)["headers"]
