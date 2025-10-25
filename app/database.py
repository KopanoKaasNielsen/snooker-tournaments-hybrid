from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
# app/database.py
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy import create_engine, MetaData

# (optional) naming convention helps with migrations & alembic
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

DATABASE_URL = "sqlite:///./snooker.db"



metadata = MetaData(naming_convention=naming_convention)

Base = declarative_base(metadata=metadata)

# Import models to ensure metadata is populated before table creation.
from . import models  # noqa: F401  pylint: disable=wrong-import-position

# typical app engine here; tests will override
SQLALCHEMY_DATABASE_URL = "sqlite:///./snooker.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

# Recreate tables for the default application database to keep the schema in sync
# with the SQLAlchemy models during tests.
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)





def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
