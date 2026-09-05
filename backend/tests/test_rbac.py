from fastapi.testclient import TestClient

from app.domain.service import Service

from tests.constants import (
    PAYMENTS_INCIDENT_ID,
    PAYMENTS_SERVICE_ID,
    SECOND_INCIDENT_ID,
    THIRD_INCIDENT_ID,
)


SERVICES_URL = "/api/v1/services"
INCIDENTS_URL = "/api/v1/incidents"

PAYLOAD = {
    "name": "Orders API",
    "owner": "Commerce Team",
    "status": "Healthy",
    "uptime": "99.95%",
    "latencyMs": 55,
    "description": (
        "Processes customer orders."
    ),
    "region": "us-east-1",
    "version": "1.0.0",
    "lastDeployedAt": (
        "2026-09-05T09:00:00Z"
    ),
    "dependencies": [
        "Payments API",
    ],
}


def test_viewer_can_list_services(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.get(
        SERVICES_URL,
        headers=viewer_headers,
    )

    assert response.status_code == 200
    
    
def test_viewer_cannot_create_service(
    client: TestClient,
    viewer_headers: dict[str, str],
) -> None:
    response = client.post(
        SERVICES_URL,
        json=PAYLOAD,
        headers=viewer_headers,
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "You do not have permission "
            "to perform this action."
        )
    }
    
    
def test_operator_can_create_service(
    client: TestClient,
    operator_headers: dict[str, str],
) -> None:
    response = client.post(
        SERVICES_URL,
        json=PAYLOAD,
        headers=operator_headers,
    )

    assert response.status_code == 201
    
    
def test_operator_cannot_delete_service(
    client: TestClient,
    operator_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=operator_headers,
    )

    assert response.status_code == 403
    
    
def test_admin_can_delete_service(
    client: TestClient,
    admin_headers: dict[str, str],
    seeded_services: list[Service],
) -> None:
    response = client.delete(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=admin_headers,
    )

    assert response.status_code == 204
    
    
def test_operator_can_update_incident(
    client: TestClient,
    operator_headers: dict[str, str],
    seeded_incidents,
) -> None:
    response = client.patch(
        (
            f"{INCIDENTS_URL}/"
            f"{PAYMENTS_INCIDENT_ID}"
        ),
        json={
            "assignee": "SRE Team",
        },
        headers=operator_headers,
    )

    assert response.status_code == 200
    
    
def test_operator_cannot_delete_incident(
    client: TestClient,
    operator_headers: dict[str, str],
    seeded_incidents,
) -> None:
    response = client.delete(
        (
            f"{INCIDENTS_URL}/"
            f"{PAYMENTS_INCIDENT_ID}"
        ),
        headers=operator_headers,
    )

    assert response.status_code == 403
    
    
def test_admin_can_delete_incident(
    client: TestClient,
    admin_headers: dict[str, str],
    seeded_incidents,
) -> None:
    response = client.delete(
        (
            f"{INCIDENTS_URL}/"
            f"{PAYMENTS_INCIDENT_ID}"
        ),
        headers=admin_headers,
    )

    assert response.status_code == 204
    
    
def test_anonymous_delete_service_returns_401(
    client: TestClient,
) -> None:
    response = client.delete(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}"
    )

    assert response.status_code == 401
    
    
def test_viewer_delete_service_returns_403(
    client: TestClient,
    viewer_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    response = client.delete(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=viewer_headers,
    )

    assert response.status_code == 403