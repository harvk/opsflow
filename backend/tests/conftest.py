from collections.abc import (
    Generator,
)

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
)

from uuid import (
    uuid4,
)

import pytest

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy import (
    create_engine,
    text,
)

from sqlalchemy.orm import (
    Session,
)

from app.api.dependencies import (
    get_login_throttle,
    get_password_reset_throttle,
    get_ses_client,
)

from app.core.config import (
    settings,
)

from app.core.login_throttle import (
    InMemoryLoginThrottle,
)

from app.core.password_reset_throttle import (
    InMemoryPasswordResetThrottle,
)

from app.core.security import (
    create_access_token,
)

from app.db.session import (
    get_db_session,
)

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)

from app.domain.service import (
    Service,
    ServiceStatus,
)

from app.domain.user import (
    User,
    UserRole,
)

from app.main import (
    app,
)

from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)

from app.repositories.sqlalchemy_service_repository import (
    SqlAlchemyServiceRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.user_service import (
    UserService,
)

from tests.constants import (
    PAYMENTS_INCIDENT_ID,
    PAYMENTS_SERVICE_ID,
    SECOND_INCIDENT_ID,
    THIRD_INCIDENT_ID,
)


# =========================================================
# TEST DATABASE ENGINE
# =========================================================


test_engine = (
    create_engine(
        settings.test_database_url,
        pool_pre_ping=True,
    )
)


# =========================================================
# TEST SES CLIENT
# =========================================================


class SuccessfulTestSesClient:
    """
    No-network SES v2 test double.

    Ordinary pytest requests should exercise the real:

        FastAPI dependency graph
            ↓
        PasswordResetDeliveryCoordinator
            ↓
        PasswordResetLinkBuilder
            ↓
        SesPasswordResetDelivery

    without ever contacting AWS.

    Tests that specifically exercise SES failure and recovery
    can replace get_ses_client with their own test doubles.

    This class deliberately implements the same minimal
    send_email contract used by SesClient.
    """

    def send_email(
        self,
        **_kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        return {
            "MessageId": (
                "pytest-password-reset-message"
            ),
        }


# =========================================================
# DATABASE SESSION
# =========================================================


@pytest.fixture
def db_session(
) -> Generator[
    Session,
    None,
    None,
]:
    """
    Creates one transaction-controlled SQLAlchemy Session
    for each test.

    The fixture also performs several safety checks before
    yielding the Session:

        1. verify pytest is connected to opsflow_test
        2. verify core application tables exist
        3. verify authentication-session tables exist
        4. verify password-reset tables exist

    This prevents migration drift from surfacing later as
    confusing PostgreSQL UndefinedTable errors.

    Test data is seeded by dedicated fixtures such as
    seeded_services and seeded_incidents.
    """

    # =====================================================
    # OPEN TEST DATABASE CONNECTION
    # =====================================================

    connection = (
        test_engine.connect()
    )

    # =====================================================
    # START OUTER TEST TRANSACTION
    # =====================================================

    # Every test runs inside this outer transaction.
    #
    # At the end of the test we roll this transaction back,
    # which removes all rows created or changed by that test.

    transaction = (
        connection.begin()
    )

    # =====================================================
    # CREATE TEST SQLALCHEMY SESSION
    # =====================================================

    session = (
        Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,

            # Nested transactions/savepoints created by
            # request fixtures can safely participate in
            # this outer test transaction.
            join_transaction_mode=(
                "create_savepoint"
            ),
        )
    )

    try:
        # =================================================
        # VERIFY CORRECT DATABASE
        # =================================================

        database_name = (
            session.execute(
                text(
                    "SELECT current_database()"
                )
            )
            .scalar_one()
        )

        if (
            database_name
            != "opsflow_test"
        ):
            raise RuntimeError(
                "Tests are connected to the wrong database. "
                "Expected 'opsflow_test', "
                f"got '{database_name}'."
            )

        # =================================================
        # VERIFY REQUIRED TABLES EXIST
        # =================================================

        # -------------------------------------------------
        # services
        # -------------------------------------------------

        services_table = (
            session.execute(
                text(
                    "SELECT to_regclass("
                    "'public.services'"
                    ")"
                )
            )
            .scalar_one()
        )

        # -------------------------------------------------
        # incidents
        # -------------------------------------------------

        incidents_table = (
            session.execute(
                text(
                    "SELECT to_regclass("
                    "'public.incidents'"
                    ")"
                )
            )
            .scalar_one()
        )

        # -------------------------------------------------
        # auth_sessions
        # -------------------------------------------------

        auth_sessions_table = (
            session.execute(
                text(
                    "SELECT to_regclass("
                    "'public.auth_sessions'"
                    ")"
                )
            )
            .scalar_one()
        )

        # -------------------------------------------------
        # password_reset_tokens
        # -------------------------------------------------

        password_reset_tokens_table = (
            session.execute(
                text(
                    "SELECT to_regclass("
                    "'public.password_reset_tokens'"
                    ")"
                )
            )
            .scalar_one()
        )

        # =================================================
        # FAIL EARLY IF SCHEMA IS INCOMPLETE
        # =================================================

        if (
            services_table
            is None
        ):
            raise RuntimeError(
                "public.services is missing "
                "from opsflow_test."
            )

        if (
            incidents_table
            is None
        ):
            raise RuntimeError(
                "public.incidents is missing "
                "from opsflow_test."
            )

        if (
            auth_sessions_table
            is None
        ):
            raise RuntimeError(
                "public.auth_sessions is missing "
                "from opsflow_test. "
                "Run the required Alembic migrations "
                "against the test database."
            )

        if (
            password_reset_tokens_table
            is None
        ):
            raise RuntimeError(
                "public.password_reset_tokens is missing "
                "from opsflow_test. "
                "Run the latest password-reset Alembic "
                "migration against the test database."
            )

        # =================================================
        # HAND SESSION TO TEST
        # =================================================

        yield session

    finally:
        # =================================================
        # TEST CLEANUP
        # =================================================

        session.close()

        # Remove every database change made by the test.
        #
        # This includes:
        #
        #   services
        #   dependencies
        #   incidents
        #   users
        #   auth_sessions
        #   password_reset_tokens
        #   password changes
        #   session revocations
        #
        # Nothing from one test should leak into the next.

        transaction.rollback()

        connection.close()


# =========================================================
# SEEDED SERVICES
# =========================================================


@pytest.fixture
def seeded_services(
    db_session: Session,
) -> list[
    Service
]:
    service_repository = (
        SqlAlchemyServiceRepository(
            db_session
        )
    )

    payments_service = (
        Service(
            id=(
                PAYMENTS_SERVICE_ID
            ),
            name=(
                "Payments API"
            ),
            owner=(
                "Payments Team"
            ),
            status=(
                ServiceStatus.HEALTHY
            ),
            uptime=(
                "99.99%"
            ),
            latency_ms=42,
            description=(
                "Processes customer payments."
            ),
            region=(
                "us-east-1"
            ),
            version=(
                "2.4.1"
            ),
            last_deployed_at=(
                datetime.now(
                    timezone.utc
                )
            ),
            dependencies=[
                "Identity API",
                "PostgreSQL",
            ],
            incidents=[],
        )
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


# =========================================================
# SEEDED INCIDENTS
# =========================================================


@pytest.fixture
def seeded_incidents(
    db_session: Session,
    seeded_services: list[
        Service
    ],
) -> list[
    Incident
]:
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

    now = (
        datetime.now(
            timezone.utc
        )
    )

    incidents = [
        Incident(
            id=(
                PAYMENTS_INCIDENT_ID
            ),
            service_id=(
                PAYMENTS_SERVICE_ID
            ),
            title=(
                "Elevated payment latency"
            ),
            severity=(
                IncidentSeverity.SEV_2
            ),
            status=(
                IncidentStatus.INVESTIGATING
            ),
            summary=(
                "Payment latency exceeded "
                "the expected threshold."
            ),
            assignee=(
                "Payments Team"
            ),
            source=(
                "monitoring"
            ),
            customer_impacting=True,
            acknowledged_at=now,
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        ),
        Incident(
            id=(
                SECOND_INCIDENT_ID
            ),
            service_id=(
                PAYMENTS_SERVICE_ID
            ),
            title=(
                "Payment error spike"
            ),
            severity=(
                IncidentSeverity.SEV_1
            ),
            status=(
                IncidentStatus.MONITORING
            ),
            summary=(
                "Payment failures exceeded "
                "the expected baseline."
            ),
            assignee=(
                "Platform Team"
            ),
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        ),
        Incident(
            id=(
                THIRD_INCIDENT_ID
            ),
            service_id=(
                PAYMENTS_SERVICE_ID
            ),
            title=(
                "Payment processing delay"
            ),
            severity=(
                IncidentSeverity.SEV_3
            ),
            status=(
                IncidentStatus.RESOLVED
            ),
            summary=(
                "Payment processing experienced "
                "temporary delays."
            ),
            assignee=(
                "SRE Team"
            ),
            source=(
                "monitoring"
            ),
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


# =========================================================
# FASTAPI TEST CLIENT
# =========================================================


@pytest.fixture
def client(
    db_session: Session,
) -> Generator[
    TestClient,
    None,
    None,
]:
    """
    Run FastAPI requests against the SQLAlchemy Session
    controlled by the current pytest test.

    The test itself owns one outer database transaction.

    Every HTTP request receives its own nested transaction
    (PostgreSQL SAVEPOINT).

    This is important because expected HTTP failures such as:

        401 invalid login
        403 authorization failure
        404 missing resource
        password-reset delivery failure

    must roll back only the work performed by that request.

    They must NOT roll back successful requests that occurred
    earlier in the same test.

    At the end of the test, db_session's outer transaction is
    still rolled back by the db_session fixture so the test
    database remains clean.
    """

    def override_get_db_session(
    ):
        # Each FastAPI request receives an independent
        # savepoint inside pytest's outer transaction.
        #
        # Successful request:
        #
        #     SAVEPOINT
        #         ↓
        #     endpoint work
        #         ↓
        #     flush
        #         ↓
        #     RELEASE SAVEPOINT
        #
        # Failed request:
        #
        #     SAVEPOINT
        #         ↓
        #     endpoint raises
        #         ↓
        #     ROLLBACK TO SAVEPOINT
        #
        # Previous successful requests remain intact.

        try:
            with db_session.begin_nested():
                yield db_session

                db_session.flush()

        finally:
            # Production uses a new Session for each HTTP
            # request.
            #
            # Pytest intentionally shares one Session for the
            # entire test, so expire loaded ORM state between
            # simulated requests to prevent the identity map
            # from leaking stale request-local state.

            db_session.expire_all()

    app.dependency_overrides[
        get_db_session
    ] = (
        override_get_db_session
    )

    try:
        with TestClient(
            app
        ) as test_client:
            yield test_client

    finally:
        # Do not clear the entire override mapping here.
        #
        # Other fixtures own independent overrides such as:
        #
        #     password-reset throttle
        #     SES client
        #     delivery test doubles
        #
        # Clearing all entries from this fixture makes those
        # independent fixtures interfere with one another.

        app.dependency_overrides.pop(
            get_db_session,
            None,
        )


# =========================================================
# AUTHENTICATED USER
# =========================================================


@pytest.fixture
def authenticated_user(
    db_session: Session,
) -> User:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = (
        UserService(
            repository
        )
    )

    user = (
        service.create_user(
            email=(
                f"api-test-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "OpsFlow Test Administrator"
            ),
            password=(
                "VerySecurePassword123!"
            ),
            role=(
                UserRole.ADMIN
            ),
        )
    )

    db_session.flush()

    return user


# =========================================================
# AUTH HEADERS
# =========================================================


@pytest.fixture
def auth_headers(
    authenticated_user: User,
) -> dict[
    str,
    str,
]:
    access_token = (
        create_access_token(
            authenticated_user.id
        )
    )

    return {
        "Authorization": (
            f"Bearer {access_token}"
        )
    }


# =========================================================
# ROLE USER FACTORY
# =========================================================


def create_user_with_role(
    db_session: Session,
    role: UserRole,
) -> User:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = (
        UserService(
            repository
        )
    )

    user = (
        service.create_user(
            email=(
                f"{role.value}-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "OpsFlow Test "
                f"{role.value.title()}"
            ),
            password=(
                "VerySecurePassword123!"
            ),
            role=role,
        )
    )

    db_session.flush()

    return user


# =========================================================
# ROLE USERS
# =========================================================


@pytest.fixture
def viewer_user(
    db_session: Session,
) -> User:
    return (
        create_user_with_role(
            db_session,
            UserRole.VIEWER,
        )
    )


@pytest.fixture
def operator_user(
    db_session: Session,
) -> User:
    return (
        create_user_with_role(
            db_session,
            UserRole.OPERATOR,
        )
    )


@pytest.fixture
def admin_user(
    db_session: Session,
) -> User:
    return (
        create_user_with_role(
            db_session,
            UserRole.ADMIN,
        )
    )


# =========================================================
# ROLE HEADER FACTORY
# =========================================================


def headers_for_user(
    user: User,
) -> dict[
    str,
    str,
]:
    token = (
        create_access_token(
            user.id
        )
    )

    return {
        "Authorization": (
            f"Bearer {token}"
        )
    }


# =========================================================
# ROLE HEADERS
# =========================================================


@pytest.fixture
def viewer_headers(
    viewer_user: User,
) -> dict[
    str,
    str,
]:
    return (
        headers_for_user(
            viewer_user
        )
    )


@pytest.fixture
def operator_headers(
    operator_user: User,
) -> dict[
    str,
    str,
]:
    return (
        headers_for_user(
            operator_user
        )
    )


@pytest.fixture
def admin_headers(
    admin_user: User,
) -> dict[
    str,
    str,
]:
    return (
        headers_for_user(
            admin_user
        )
    )


# =========================================================
# LOGIN THROTTLE ISOLATION
# =========================================================


@pytest.fixture(
    autouse=True
)
def reset_login_throttle_state(
):
    """
    Keep authentication throttle state isolated between
    tests.

    Production application state is intentionally shared
    between requests; pytest tests must not share it between
    test cases.
    """

    throttle = (
        get_login_throttle()
    )

    if isinstance(
        throttle,
        InMemoryLoginThrottle,
    ):
        throttle.reset()

    yield

    if isinstance(
        throttle,
        InMemoryLoginThrottle,
    ):
        throttle.reset()


@pytest.fixture(
    autouse=True
)
def clear_process_local_login_throttle(
):
    get_login_throttle.cache_clear()

    yield

    get_login_throttle.cache_clear()


# =========================================================
# PASSWORD RESET THROTTLE ISOLATION
# =========================================================


@pytest.fixture(
    autouse=True
)
def isolate_password_reset_throttle(
):
    """
    Give every test its own password-reset throttle state.

    TestClient requests all originate from the same synthetic
    client address, so allowing the production lru-cached
    limiter to survive between tests would make unrelated
    API tests consume one another's IP quota.
    """

    throttle = (
        InMemoryPasswordResetThrottle(
            secret_key=(
                settings
                .auth_throttle_secret_key
                .get_secret_value()
            ),
            ip_max_requests=(
                settings
                .password_reset_ip_max_requests
            ),
            ip_window_seconds=(
                settings
                .password_reset_ip_window_seconds
            ),
            account_max_requests=(
                settings
                .password_reset_account_max_requests
            ),
            account_window_seconds=(
                settings
                .password_reset_account_window_seconds
            ),
        )
    )

    app.dependency_overrides[
        get_password_reset_throttle
    ] = (
        lambda: throttle
    )

    try:
        yield

    finally:
        app.dependency_overrides.pop(
            get_password_reset_throttle,
            None,
        )

        get_password_reset_throttle.cache_clear()


# =========================================================
# SES NETWORK ISOLATION
# =========================================================


@pytest.fixture(
    autouse=True
)
def isolate_ses_client(
):
    """
    Prevent ordinary pytest requests from contacting AWS SES.

    Production still uses get_ses_client() normally.

    During tests FastAPI resolves the real delivery graph,
    but the final network-facing SES dependency is replaced
    with a deterministic successful test client.

    Individual tests remain free to replace get_ses_client
    again.

    This is especially important for
    test_password_reset_delivery_resilience.py, whose
    failing_ses_client fixture replaces this override with
    its deliberate provider-failure test double.
    """

    ses_client = (
        SuccessfulTestSesClient()
    )

    # Do not allow a real boto3 client cached by some earlier
    # operation to survive into this test.

    get_ses_client.cache_clear()

    app.dependency_overrides[
        get_ses_client
    ] = (
        lambda: ses_client
    )

    try:
        yield

    finally:
        app.dependency_overrides.pop(
            get_ses_client,
            None,
        )

        get_ses_client.cache_clear()