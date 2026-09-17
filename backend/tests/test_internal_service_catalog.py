from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_incident_service_token_verifier
from app.core.service_identity import ServiceScope
from app.core.service_token_verifier import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ServiceAuthenticationError,
    ServicePrincipal,
)
from app.domain.service import Service

VALID_TOKEN = "valid-incident-service-token"
INSUFFICIENT_SCOPE_TOKEN = "insufficient-scope-token"
ISSUED_AT = datetime(
    2026,
    9,
    16,
    12,
    0,
    tzinfo=UTC,
)


def principal_with_scope(
    scope: ServiceScope,
) -> ServicePrincipal:
    return ServicePrincipal(
        issuer="opsflow-incident-service",
        subject="opsflow-incident-service",
        audience="opsflow-core-backend",
        token_id=uuid4(),
        issued_at=ISSUED_AT,
        not_before=ISSUED_AT,
        expires_at=(
            ISSUED_AT
            + timedelta(seconds=60)
        ),
        scopes=frozenset({scope}),
    )


class StubIncidentServiceTokenVerifier:
    def verify_token(
        self,
        token: str,
    ) -> ServicePrincipal:
        if token == VALID_TOKEN:
            return principal_with_scope(
                ServiceScope.SERVICES_READ
            )

        if token == INSUFFICIENT_SCOPE_TOKEN:
            return principal_with_scope(
                ServiceScope.INCIDENTS_READ
            )

        raise ServiceAuthenticationError(
            INVALID_SERVICE_CREDENTIALS_MESSAGE
        )


@pytest.fixture(autouse=True)
def override_service_verifier(
    client: TestClient,
) -> Generator[None, None, None]:
    application = cast(
        FastAPI,
        client.app,
    )
    application.dependency_overrides[
        get_incident_service_token_verifier
    ] = StubIncidentServiceTokenVerifier

    yield

    application.dependency_overrides.pop(
        get_incident_service_token_verifier,
        None,
    )


def bearer_headers(
    token: str = VALID_TOKEN,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}"
    }


def test_internal_service_endpoint_requires_bearer_token(
    client: TestClient,
) -> None:
    response = client.get(
        f"/api/v1/internal/services/{uuid4()}/exists"
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": INVALID_SERVICE_CREDENTIALS_MESSAGE
    }
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_internal_service_endpoint_rejects_invalid_token(
    client: TestClient,
) -> None:
    response = client.get(
        f"/api/v1/internal/services/{uuid4()}/exists",
        headers=bearer_headers("invalid-token"),
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": INVALID_SERVICE_CREDENTIALS_MESSAGE
    }


def test_internal_service_endpoint_rejects_legacy_header(
    client: TestClient,
) -> None:
    response = client.get(
        f"/api/v1/internal/services/{uuid4()}/exists",
        headers={
            "X-OpsFlow-Internal-Token": "x" * 32
        },
    )

    assert response.status_code == 401


def test_internal_service_endpoint_rejects_wrong_scope(
    client: TestClient,
) -> None:
    response = client.get(
        f"/api/v1/internal/services/{uuid4()}/exists",
        headers=bearer_headers(
            INSUFFICIENT_SCOPE_TOKEN
        ),
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Insufficient service permissions."
    }


def test_internal_service_endpoint_reports_existing_service(
    client: TestClient,
    seeded_services: list[Service],
) -> None:
    service_id = seeded_services[0].id
    response = client.get(
        f"/api/v1/internal/services/{service_id}/exists",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "exists": True
    }


def test_internal_service_endpoint_reports_unknown_service(
    client: TestClient,
) -> None:
    response = client.get(
        f"/api/v1/internal/services/{uuid4()}/exists",
        headers=bearer_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "exists": False
    }
