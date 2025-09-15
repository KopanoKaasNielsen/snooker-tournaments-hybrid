import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.database import get_db
from app.main import app

# Use an in-memory SQLite database for tests
TEST_SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Create tables before any tests run
@pytest.fixture(scope="session", autouse=True)
def create_test_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# Override the dependency for get_db
@pytest.fixture(autouse=True)
def override_get_db(monkeypatch):
    def _override():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
