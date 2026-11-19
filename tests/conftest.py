import os
import sys
import tempfile

# Existing tests import tests.conftest directly; share the same fixture engine.
sys.modules.setdefault("tests.conftest", sys.modules[__name__])

# Isolate all application connections before imports; no implicit demo seeding.
_test_directory = tempfile.TemporaryDirectory(prefix="snooker-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_directory.name}/seed.db"

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
