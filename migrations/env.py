"""Alembic uses the same lazy configuration and metadata as the application."""

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401
from app.database import Base, get_database_url, make_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)
target_metadata = Base.metadata

# Programmatic tests may supply an explicit URL without changing process configuration.
url = config.attributes.get("database_url") or get_database_url()


def run_migrations_offline():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # SQLite batch recreation needs FK enforcement disabled on this dedicated connection.
    # Check all references before commit, then dispose. Application engines always enforce FKs.
    connectable = make_engine(url, foreign_keys=False)
    try:
        with connectable.connect() as connection:
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql(
                    "BEGIN"
                )  # transactional DDL with sqlite3 legacy mode
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                compare_type=True,
            )
            try:
                with context.begin_transaction():
                    context.run_migrations()
                    if connection.dialect.name == "sqlite":
                        if connection.exec_driver_sql(
                            "PRAGMA foreign_key_check"
                        ).fetchall():
                            raise RuntimeError(
                                "Foreign key violations: migration rolled back"
                            )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
