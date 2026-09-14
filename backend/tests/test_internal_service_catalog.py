from uuid import (
    uuid4,
)

from fastapi.testclient import (
    TestClient,
)

from app.core.config import (
    settings,
)
from app.domain.service import (
    Service,
)


def internal_headers(
) -> dict[
    str,
    str,
]:
    return {
        "X-OpsFlow-Internal-Token": (
            settings
            .incident_service_token
            .get_secret_value()
        ),
    }


def test_internal_service_endpoint_requires_token(
    client: TestClient,
) -> None:
    response = client.get(
        
            "/api/v1/internal/services/"
            f"{uuid4()}/exists"
        
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": (
            "Invalid internal service credentials."
        ),
    }


def test_internal_service_endpoint_rejects_invalid_token(
    client: TestClient,
) -> None:
    response = client.get(
        (
            "/api/v1/internal/services/"
            f"{uuid4()}/exists"
        ),
        headers={
            "X-OpsFlow-Internal-Token": (
                "x" * 32
            ),
        },
    )

    assert response.status_code == 401


def test_internal_service_endpoint_reports_existing_service(
    client: TestClient,
    seeded_services: list[
        Service
    ],
) -> None:
    service_id = (
        seeded_services[0]
        .id
    )

    response = client.get(
        (
            "/api/v1/internal/services/"
            f"{service_id}/exists"
        ),
        headers=internal_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "exists": True,
    }


def test_internal_service_endpoint_reports_unknown_service(
    client: TestClient,
) -> None:
    response = client.get(
        (
            "/api/v1/internal/services/"
            f"{uuid4()}/exists"
        ),
        headers=internal_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "exists": False,
    }