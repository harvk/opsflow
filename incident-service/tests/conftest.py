from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

INCIDENT_SERVICE_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

load_dotenv(
    INCIDENT_SERVICE_DIR / ".env",
    override=False,
)


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    test_database_url = (
        os.environ
        .get(
            "TEST_DATABASE_URL",
            "",
        )
        .strip()
    )

    if not test_database_url:
        raise RuntimeError(
            "TEST_DATABASE_URL must be configured in "
            "incident-service/.env before persistence "
            "tests can run."
        )

    engine = create_engine(
        test_database_url,
        pool_pre_ping=True,
    )

    with engine.connect() as connection:
        database_name = connection.execute(
            text(
                "SELECT current_database()"
            )
        ).scalar_one()

        if database_name != "opsflow_incidents_test":
            raise RuntimeError(
                "Incident persistence tests are connected "
                "to the wrong database. Expected "
                "'opsflow_incidents_test', "
                f"got '{database_name}'."
            )

        incidents_table = connection.execute(
            text(
                "SELECT to_regclass("
                "'public.incidents'"
                ")"
            )
        ).scalar_one()

        if incidents_table is None:
            raise RuntimeError(
                "public.incidents is missing from "
                "opsflow_incidents_test. Run the Incident "
                "Service Alembic migration first."
            )

        migration_version = connection.execute(
            text(
                "SELECT version_num "
                "FROM alembic_version"
            )
        ).scalar_one()

        if migration_version != "1c4b8e2a9d57":
            raise RuntimeError(
                "Incident test database is at the wrong "
                "migration revision. Expected "
                "'1c4b8e2a9d57', "
                f"got '{migration_version}'."
            )

    try:
        yield engine

    finally:
        engine.dispose()


@pytest.fixture
def db_session(
    test_engine: Engine,
) -> Generator[Session, None, None]:
    connection = test_engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session

    finally:
        session.close()
        transaction.rollback()
        connection.close()