from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from controlcheck.persistence.database import Base
from controlcheck.persistence import action_models, governance_models, models  # noqa: F401


config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

env_database_url = (
    os.environ.get("CONTROLCHECK_DATABASE_URL", "").strip()
    or os.environ.get("DATABASE_URL", "").strip()
)
if env_database_url:
    if env_database_url.startswith("postgresql://"):
        env_database_url = "postgresql+psycopg://" + env_database_url[len("postgresql://"):]
    elif env_database_url.startswith("postgres://"):
        env_database_url = "postgresql+psycopg://" + env_database_url[len("postgres://"):]
    config.set_main_option("sqlalchemy.url", env_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
