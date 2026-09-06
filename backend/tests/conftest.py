from collections.abc import Generator
from datetime import datetime, timezone

from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db_session

from app.core.security import create_access_token

from app.domain.user import User, UserRole
from app.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository
from app.services.user_service import UserService

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
def db_session() -> Generator[
    Session,
    None,
    None,
]:
    """
    Creates one transaction-controlled SQLAlchemy Session
    for each test.

    Test data is seeded by dedicated fixtures such as
    seeded_services and seeded_incidents.
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
            text(
                "SELECT current_database()"
            )
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

        yield session

    finally:
        session.close()

        # Removes every change made by the test:
        # Services, dependencies, Incidents,
        # PATCHes, users, etc.
        transaction.rollback()

        connection.close()
        
        
@pytest.fixture
def seeded_services(
    db_session: Session,
) -> list[Service]:
    service_repository = (
        SqlAlchemyServiceRepository(
            db_session
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
        incidents=[],
    )

    service_repository.create(
        payments_service
    )

    # Make the inserted Service visible to all operations
    # using this test transaction.
    db_session.flush()

    return [
        payments_service
    ]


@pytest.fixture
def seeded_incidents(
    db_session: Session,
    seeded_services: list[Service]
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
            source="monitoring",
            customer_impacting=True,
            acknowledged_at=now,
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
            source="monitoring",
            customer_impacting=False,
            acknowledged_at=now,
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
        
@pytest.fixture
def authenticated_user(
    db_session,
) -> User:
    repository = SqlAlchemyUserRepository(
        db_session
    )

    service = UserService(
        repository
    )

    user = service.create_user(
        email=(
            f"api-test-{uuid4().hex}"
            "@example.com"
        ),
        full_name="OpsFlow Test Administrator",
        password="VerySecurePassword123!",
        role=UserRole.ADMIN,
    )

    db_session.flush()

    return user


@pytest.fixture
def auth_headers(
    authenticated_user: User,
) -> dict[str, str]:
    access_token = create_access_token(
        authenticated_user.id
    )

    return {
        "Authorization": (
            f"Bearer {access_token}"
        )
    }

    
def create_user_with_role(
    db_session,
    role: UserRole,
) -> User:
    repository = SqlAlchemyUserRepository(
        db_session
    )

    service = UserService(
        repository
    )

    user = service.create_user(
        email=(
            f"{role.value}-"
            f"{uuid4().hex}@example.com"
        ),
        full_name=(
            f"OpsFlow Test {role.value.title()}"
        ),
        password="VerySecurePassword123!",
        role=role,
    )

    db_session.flush()

    return user


@pytest.fixture
def viewer_user(
    db_session,
) -> User:
    return create_user_with_role(
        db_session,
        UserRole.VIEWER,
    )


@pytest.fixture
def operator_user(
    db_session,
) -> User:
    return create_user_with_role(
        db_session,
        UserRole.OPERATOR,
    )


@pytest.fixture
def admin_user(
    db_session,
) -> User:
    return create_user_with_role(
        db_session,
        UserRole.ADMIN,
    )
    

def headers_for_user(
    user: User,
) -> dict[str, str]:
    token = create_access_token(
        user.id
    )

    return {
        "Authorization": (
            f"Bearer {token}"
        )
    }
    
    
@pytest.fixture
def viewer_headers(
    viewer_user: User,
) -> dict[str, str]:
    return headers_for_user(
        viewer_user
    )


@pytest.fixture
def operator_headers(
    operator_user: User,
) -> dict[str, str]:
    return headers_for_user(
        operator_user
    )


@pytest.fixture
def admin_headers(
    admin_user: User,
) -> dict[str, str]:
    return headers_for_user(
        admin_user
    )