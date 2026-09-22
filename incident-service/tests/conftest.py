from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
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


def get_expected_migration_head() -> str:
    """
    Resolve the current Incident Service Alembic head directly
    from the migration files.

    This prevents the test fixture from requiring a manually
    hard-coded migration revision every time a new migration
    is created.
    """

    alembic_config = Config(
        str(
            INCIDENT_SERVICE_DIR
            / "alembic.ini"
        )
    )

    alembic_config.set_main_option(
        "script_location",
        str(
            INCIDENT_SERVICE_DIR
            / "migrations"
        ),
    )

    script_directory = (
        ScriptDirectory.from_config(
            alembic_config
        )
    )

    head_revision = (
        script_directory
        .get_current_head()
    )

    if head_revision is None:
        raise RuntimeError(
            "Incident Service Alembic has no current "
            "migration head."
        )

    return head_revision


@pytest.fixture(
    scope="session",
)
def test_engine(
) -> Generator[
    Engine,
    None,
    None,
]:
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
        database_name = (
            connection.execute(
                text(
                    "SELECT current_database()"
                )
            )
            .scalar_one()
        )

        if (
            database_name
            != "opsflow_incidents_test"
        ):
            raise RuntimeError(
                "Incident persistence tests are connected "
                "to the wrong database. Expected "
                "'opsflow_incidents_test', "
                f"got '{database_name}'."
            )

        incidents_table = (
            connection.execute(
                text(
                    "SELECT to_regclass("
                    "'public.incidents'"
                    ")"
                )
            )
            .scalar_one()
        )

        if incidents_table is None:
            raise RuntimeError(
                "public.incidents is missing from "
                "opsflow_incidents_test. Run the Incident "
                "Service Alembic migration first."
            )

        incident_task_outbox_table = (
            connection.execute(
                text(
                    "SELECT to_regclass("
                    "'public.incident_task_outbox'"
                    ")"
                )
            )
            .scalar_one()
        )

        if (
            incident_task_outbox_table
            is None
        ):
            raise RuntimeError(
                "public.incident_task_outbox is missing "
                "from opsflow_incidents_test. Run the "
                "latest Incident Service Alembic "
                "migration against the test database."
            )

        incident_task_completion_outbox_table = (
            connection.execute(
                text(
                    "SELECT to_regclass("
                    "'public.incident_task_completion_outbox'"
                    ")"
                )
            )
            .scalar_one()
        )

        if (
            incident_task_completion_outbox_table
            is None
        ):
            raise RuntimeError(
                "public.incident_task_completion_outbox is "
                "missing from opsflow_incidents_test. Run "
                "the latest Incident Service Alembic "
                "migration against the test database."
            )

        migration_version = (
            connection.execute(
                text(
                    "SELECT version_num "
                    "FROM alembic_version"
                )
            )
            .scalar_one()
        )

        expected_migration_version = (
            get_expected_migration_head()
        )

        if (
            migration_version
            != expected_migration_version
        ):
            raise RuntimeError(
                "Incident test database is at the wrong "
                "migration revision. Expected "
                f"'{expected_migration_version}', "
                f"got '{migration_version}'."
            )

    try:
        yield engine

    finally:
        engine.dispose()


@pytest.fixture
def db_session(
    test_engine: Engine,
) -> Generator[
    Session,
    None,
    None,
]:
    connection = (
        test_engine.connect()
    )

    transaction = (
        connection.begin()
    )

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode=(
            "create_savepoint"
        ),
    )

    try:
        yield session

    finally:
        session.close()
        transaction.rollback()
        connection.close()
