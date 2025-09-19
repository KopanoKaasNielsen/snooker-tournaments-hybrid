from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
# app/database.py
from sqlalchemy.orm import declarative_base, sessionmaker
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

# typical app engine here; tests will override
SQLALCHEMY_DATABASE_URL = "sqlite:///./snooker.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)





def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
