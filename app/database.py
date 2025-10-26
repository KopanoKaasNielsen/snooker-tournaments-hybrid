"""Database configuration for the snooker tournaments application."""

from __future__ import annotations

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# (optional) naming convention helps with migrations & alembic
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)

Base = declarative_base(metadata=metadata)

# typical app engine here; tests will override
SQLALCHEMY_DATABASE_URL = "sqlite:///./snooker.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Ensure default SQLite database has tables available for ad-hoc usage
Base.metadata.create_all(bind=engine)






def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
