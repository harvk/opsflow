from __future__ import annotations

from collections.abc import Generator
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_service_catalog_gateway,
    get_service_token_verifier,
)
from app.core.config import Settings
from app.core.request_context import (
    REQUEST_ID_HEADER,
)
from app.core.service_identity import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ServiceAuthenticationError,
    ServicePrincipal,
    ServiceScope,
)
from app.db.session import get_db_session
from app.gateways.unavailable_service_catalog_gateway import (
    UnavailableServiceCatalogGateway,
)
from app.main import create_app

AUTHORIZATION_HEADER = (
    "Authorization"
)

READ_TOKEN = "test-service-token-read"
WRITE_TOKEN = "test-service-token-write"
READ_WRITE_TOKEN = (
    "test-service-token-read-write"
)


def build_service_principal(
    scopes: frozenset[
        ServiceScope
    ],
) -> ServicePrincipal:
    issued_at = datetime(
        2026,
        9,
        16,
        12,
        0,
        tzinfo=UTC,
    )

    return ServicePrincipal(
        issuer="opsflow-core-backend",
        subject="opsflow-core-backend",
        audience="opsflow-incident-service",
        token_id=uuid4(),
        issued_at=issued_at,
        not_before=issued_at,
        expires_at=(
            issued_at
            + timedelta(
                seconds=60
            )
        ),
        scopes=scopes,
    )


class StubServiceTokenVerifier:
    def __init__(
        self,
    ) -> None:
        self._principals = {
            READ_TOKEN: build_service_principal(
                frozenset(
                    {
                        ServiceScope.INCIDENTS_READ,
                    }
                )
            ),
            WRITE_TOKEN: build_service_principal(
                frozenset(
                    {
                        ServiceScope.INCIDENTS_WRITE,
                    }
                )
            ),
            READ_WRITE_TOKEN: build_service_principal(
                frozenset(
                    {
                        ServiceScope.INCIDENTS_READ,
                        ServiceScope.INCIDENTS_WRITE,
                    }
                )
            ),
        }

    def verify_token(
        self,
        token: str,
    ) -> ServicePrincipal:
        principal = self._principals.get(
            token
        )

        if principal is None:
            raise ServiceAuthenticationError(
                INVALID_SERVICE_CREDENTIALS_MESSAGE
            )

        return principal


class StubServiceCatalogGateway:
    def __init__(
        self,
        existing_service_ids: set[UUID],
    ) -> None:
        self._existing_service_ids = (
            existing_service_ids
        )

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        return (
            service_id
            in self._existing_service_ids
        )


def build_test_settings(
) -> Settings:
    return Settings(
        app_name=(
            "OpsFlow Incident Service"
        ),
        app_env="test",
        api_v1_prefix="/api/v1",
        database_url=(
            "postgresql+psycopg://"
            "test:test@localhost/test"
        ),
        core_backend_url=(
            "http://core-backend.test"
            "/api/v1"
        ),
    )


@pytest.fixture
def security_client(
) -> Generator[
    TestClient,
    None,
    None,
]:
    application = create_app(
        build_test_settings()
    )

    token_verifier = (
        StubServiceTokenVerifier()
    )

    application.dependency_overrides[
        get_service_token_verifier
    ] = lambda: token_verifier

    with TestClient(
        application
    ) as client:
        yield client

    application.dependency_overrides.clear()


@pytest.fixture
def api_client(
    db_session: Session,
) -> Generator[
    tuple[TestClient, UUID],
    None,
    None,
]:
    service_id = uuid4()

    application = create_app(
        build_test_settings()
    )

    def override_db_session(
    ) -> Generator[
        Session,
        None,
        None,
    ]:
        yield db_session

    application.dependency_overrides[
        get_db_session
    ] = override_db_session

    application.dependency_overrides[
        get_service_catalog_gateway
    ] = lambda: (
        StubServiceCatalogGateway(
            {
                service_id
            }
        )
    )

    token_verifier = (
        StubServiceTokenVerifier()
    )

    application.dependency_overrides[
        get_service_token_verifier
    ] = lambda: token_verifier

    with TestClient(
        application
    ) as client:
        client.headers.update(
            {
                AUTHORIZATION_HEADER: (
                    "Bearer "
                    f"{READ_WRITE_TOKEN}"
                )
            }
        )

        yield client, service_id

    application.dependency_overrides.clear()


# =========================================================
# AUTHENTICATION CONTRACT
# =========================================================

def test_health_does_not_require_service_token(
    security_client: TestClient,
) -> None:
    response = security_client.get(
        "/api/v1/health"
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "authorization_header",
    [
        None,
        "",
        "Basic not-a-service-token",
        "Bearer",
        "Bearer invalid-service-token",
    ],
)
def test_incident_api_rejects_invalid_service_credentials(
    security_client: TestClient,
    authorization_header: str | None,
) -> None:
    request_headers: dict[
        str,
        str,
    ] = {}

    if authorization_header is not None:
        request_headers[
            AUTHORIZATION_HEADER
        ] = authorization_header

    response = security_client.get(
        "/api/v1/incidents",
        headers=request_headers,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            INVALID_SERVICE_CREDENTIALS_MESSAGE
        )
    }

    assert response.headers[
        "WWW-Authenticate"
    ] == "Bearer"


def test_read_scope_cannot_create_incident(
    security_client: TestClient,
) -> None:
    service_id = uuid4()

    response = security_client.post(
        "/api/v1/incidents",
        headers={
            AUTHORIZATION_HEADER: (
                f"Bearer {READ_TOKEN}"
            )
        },
        json={
            "title": "Scope enforcement",
            "serviceId": str(
                service_id
            ),
            "severity": "SEV-3",
            "summary": (
                "A read identity cannot write."
            ),
            "assignee": (
                "Platform Operations"
            ),
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Insufficient service permissions."
        )
    }


def test_write_scope_cannot_list_incidents(
    security_client: TestClient,
) -> None:
    response = security_client.get(
        "/api/v1/incidents",
        headers={
            AUTHORIZATION_HEADER: (
                f"Bearer {WRITE_TOKEN}"
            )
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "Insufficient service permissions."
        )
    }


# =========================================================
# INCIDENT CRUD CONTRACT
# =========================================================

def test_incident_crud_contract(
    api_client: tuple[
        TestClient,
        UUID,
    ],
) -> None:
    client, service_id = api_client

    create_response = client.post(
        "/api/v1/incidents",
        json={
            "title": (
                "Elevated API latency"
            ),
            "serviceId": str(
                service_id
            ),
            "severity": "SEV-2",
            "status": "Investigating",
            "summary": (
                "Requests exceed the "
                "latency target."
            ),
            "assignee": (
                "Platform Operations"
            ),
            "source": "monitoring",
            "customerImpacting": True,
        },
    )

    assert (
        create_response.status_code
        == 201
    )

    created = create_response.json()

    incident_id = created[
        "id"
    ]

    assert (
        created["serviceId"]
        == str(service_id)
    )

    assert (
        created["severity"]
        == "SEV-2"
    )

    assert (
        created["status"]
        == "Investigating"
    )

    assert (
        created["source"]
        == "monitoring"
    )

    assert (
        created[
            "customerImpacting"
        ]
        is True
    )

    get_response = client.get(

            "/api/v1/incidents/"
            f"{incident_id}"

    )

    assert (
        get_response.status_code
        == 200
    )

    assert (
        get_response.json()["id"]
        == incident_id
    )

    list_response = client.get(
        "/api/v1/incidents",
        params={
            "serviceId": str(
                service_id
            ),
            "severity": "SEV-2",
            "status": "Investigating",
        },
    )

    assert (
        list_response.status_code
        == 200
    )

    assert [
        incident["id"]
        for incident
        in list_response.json()
    ] == [
        incident_id
    ]

    update_response = client.patch(
        (
            "/api/v1/incidents/"
            f"{incident_id}"
        ),
        json={
            "status": "Resolved",
            "summary": (
                "Latency returned "
                "to normal."
            ),
            "customerImpacting": False,
        },
    )

    assert (
        update_response.status_code
        == 200
    )

    updated = (
        update_response.json()
    )

    assert (
        updated["status"]
        == "Resolved"
    )

    assert (
        updated["summary"]
        == "Latency returned to normal."
    )

    assert (
        updated[
            "customerImpacting"
        ]
        is False
    )

    assert (
        updated["resolvedAt"]
        is not None
    )

    delete_response = client.delete(

            "/api/v1/incidents/"
            f"{incident_id}"

    )

    assert (
        delete_response.status_code
        == 204
    )

    missing_response = client.get(

            "/api/v1/incidents/"
            f"{incident_id}"

    )

    assert (
        missing_response.status_code
        == 404
    )


def test_create_rejects_unknown_service_reference(
    api_client: tuple[
        TestClient,
        UUID,
    ],
) -> None:
    client, _service_id = api_client

    unknown_service_id = uuid4()

    response = client.post(
        "/api/v1/incidents",
        json={
            "title": (
                "Unknown service incident"
            ),
            "serviceId": str(
                unknown_service_id
            ),
            "severity": "SEV-3",
            "summary": (
                "Unknown service reference."
            ),
            "assignee": (
                "Platform Operations"
            ),
        },
    )

    assert response.status_code == 404

    assert str(
        unknown_service_id
    ) in response.json()[
        "detail"
    ]


def test_get_returns_not_found_for_unknown_incident(
    api_client: tuple[
        TestClient,
        UUID,
    ],
) -> None:
    client, _service_id = api_client

    incident_id = uuid4()

    response = client.get(

            "/api/v1/incidents/"
            f"{incident_id}"

    )

    assert response.status_code == 404

    assert str(
        incident_id
    ) in response.json()[
        "detail"
    ]


# =========================================================
# FAIL-CLOSED SERVICE CATALOG CONTRACT
# =========================================================

def test_create_fails_closed_when_catalog_is_unavailable(
    db_session: Session,
) -> None:
    application = create_app(
        build_test_settings()
    )

    def override_db_session(
    ) -> Generator[
        Session,
        None,
        None,
    ]:
        yield db_session

    application.dependency_overrides[
        get_db_session
    ] = override_db_session

    application.dependency_overrides[
        get_service_catalog_gateway
    ] = lambda: (
        UnavailableServiceCatalogGateway()
    )

    token_verifier = (
        StubServiceTokenVerifier()
    )

    application.dependency_overrides[
        get_service_token_verifier
    ] = lambda: token_verifier

    with TestClient(
        application
    ) as client:
        client.headers.update(
            {
                AUTHORIZATION_HEADER: (
                    "Bearer "
                    f"{READ_WRITE_TOKEN}"
                )
            }
        )

        response = client.post(
            "/api/v1/incidents",
            json={
                "title": (
                    "Catalog unavailable"
                ),
                "serviceId": str(
                    uuid4()
                ),
                "severity": "SEV-2",
                "summary": (
                    "Catalog validation "
                    "is unavailable."
                ),
                "assignee": (
                    "Platform Operations"
                ),
            },
        )

    application.dependency_overrides.clear()

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        .startswith(
            "Service Catalog validation "
            "is unavailable."
        )
    )


def test_authentication_failure_preserves_request_id(
    security_client: TestClient,
) -> None:
    supplied_request_id = (
        "private-api-auth-failure:9.6.4"
    )

    response = security_client.get(
        "/api/v1/incidents",
        headers={
            AUTHORIZATION_HEADER: (
                "Bearer invalid-service-token"
            ),
            REQUEST_ID_HEADER: (
                supplied_request_id
            ),
        },
    )

    assert response.status_code == 401

    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == supplied_request_id
    )
