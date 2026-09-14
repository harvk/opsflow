from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from app.db.base_metadata import Base

INCIDENT_SERVICE_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

load_dotenv(
    INCIDENT_SERVICE_DIR / ".env",
    override=False,
)

config = context.config


def get_database_url() -> str:
    database_url = (
        os.environ
        .get(
            "DATABASE_URL",
            "",
        )
        .strip()
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL must be set before "
            "Incident Service migrations can run."
        )

    return database_url


def escape_alembic_config_value(
    value: str,
) -> str:
    return value.replace(
        "%",
        "%%",
    )


config.set_main_option(
    "sqlalchemy.url",
    escape_alembic_config_value(
        get_database_url()
    ),
)

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option(
            "sqlalchemy.url"
        ),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()