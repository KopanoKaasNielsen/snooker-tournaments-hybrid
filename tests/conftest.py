import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # ensure models are registered
from app.database import Base, get_db
from app.main import app

TEST_SQLITE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_SQLITE_URL, connect_args={"check_same_thread": False})
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
def override_get_db(monkeypatch):
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
