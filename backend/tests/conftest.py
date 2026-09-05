from collections.abc import Generator
from datetime import datetime, timezone

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.service import (
    Service,
    ServiceStatus,
)

from app.main import app

from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.repositories.sqlalchemy_service_repository import (
    SqlAlchemyServiceRepository,
)

from tests.constants import (
    PAYMENTS_INCIDENT_ID,
    PAYMENTS_SERVICE_ID,
    SECOND_INCIDENT_ID,
    THIRD_INCIDENT_ID,
)


test_engine = create_engine(
    settings.test_database_url,
    pool_pre_ping=True,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """
    Creates one transaction-controlled SQLAlchemy Session
    for each test.

    The base Service record is inserted here because both
    Service tests and Incident tests depend on it.
    """

    connection = test_engine.connect()

    transaction = connection.begin()

    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        database_name = session.execute(
            text("SELECT current_database()")
        ).scalar_one()

        if database_name != "opsflow_test":
            raise RuntimeError(
                "Tests are connected to the wrong database. "
                f"Expected 'opsflow_test', got '{database_name}'."
            )

        services_table = session.execute(
            text(
                "SELECT to_regclass("
                "'public.services'"
                ")"
            )
        ).scalar_one()

        incidents_table = session.execute(
            text(
                "SELECT to_regclass("
                "'public.incidents'"
                ")"
            )
        ).scalar_one()

        if services_table is None:
            raise RuntimeError(
                "public.services is missing "
                "from opsflow_test."
            )

        if incidents_table is None:
            raise RuntimeError(
                "public.incidents is missing "
                "from opsflow_test."
            )

        service_repository = (
            SqlAlchemyServiceRepository(
                session
            )
        )

        payments_service = Service(
            id=PAYMENTS_SERVICE_ID,
            name="Payments API",
            owner="Payments Team",
            status=ServiceStatus.HEALTHY,
            uptime="99.99%",
            latency_ms=42,
            description=(
                "Processes customer payments."
            ),
            region="us-east-1",
            version="2.4.1",
            last_deployed_at=datetime.now(
                timezone.utc
            ),
            dependencies=[
                "Identity API",
                "PostgreSQL",
            ],
        )

        service_repository.create(
            payments_service
        )

        # Make the INSERT visible inside this transaction.
        session.flush()

        yield session

    finally:
        session.close()

        # Removes every change made by the test:
        # Services, dependencies, Incidents, PATCHes, etc.
        transaction.rollback()

        connection.close()


@pytest.fixture
def seeded_incidents(
    db_session: Session,
) -> list[Incident]:
    """
    Adds Incident rows to the SAME Session/transaction
    created by db_session.

    Tests that need existing Incidents request this fixture.
    """

    incident_repository = (
        SqlAlchemyIncidentRepository(
            db_session
        )
    )

    now = datetime.now(
        timezone.utc
    )

    incidents = [
        Incident(
            id=PAYMENTS_INCIDENT_ID,
            service_id=PAYMENTS_SERVICE_ID,
            title="Elevated payment latency",
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.INVESTIGATING,
            summary=(
                "Payment latency exceeded "
                "the expected threshold."
            ),
            assignee="Payments Team",
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        ),
        Incident(
            id=SECOND_INCIDENT_ID,
            service_id=PAYMENTS_SERVICE_ID,
            title="Payment error spike",
            severity=IncidentSeverity.SEV_1,
            status=IncidentStatus.MONITORING,
            summary=(
                "Payment failures exceeded "
                "the expected baseline."
            ),
            assignee="Platform Team",
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        ),
        Incident(
            id=THIRD_INCIDENT_ID,
            service_id=PAYMENTS_SERVICE_ID,
            title="Payment processing delay",
            severity=IncidentSeverity.SEV_3,
            status=IncidentStatus.RESOLVED,
            summary=(
                "Payment processing experienced "
                "temporary delays."
            ),
            assignee="SRE Team",
            started_at=now,
            resolved_at=now,
            created_at=now,
            updated_at=now,
        ),
    ]

    for incident in incidents:
        incident_repository.create(
            incident
        )

    db_session.flush()

    return incidents


@pytest.fixture
def client(
    db_session: Session,
) -> Generator[TestClient, None, None]:
    """
    Makes FastAPI use the exact SQLAlchemy Session controlled
    by pytest instead of creating a normal application session.
    """

    def override_get_db_session():
        try:
            yield db_session
            db_session.flush()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[
        get_db_session
    ] = override_get_db_session

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()