from uuid import UUID

from fastapi.testclient import TestClient

from app.domain.service import Service

PAYMENTS_SERVICE_ID = UUID(
    "11111111-1111-1111-1111-111111111111"
)


SERVICES_URL = "/api/v1/services"


def test_get_services_returns_200(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    response = client.get(
        SERVICES_URL,
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, list)
    assert len(body) >= 1


def test_get_service_returns_service(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    response = client.get(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(
        PAYMENTS_SERVICE_ID
    )

    assert body["name"] == "Payments API"
    assert body["latencyMs"] == 42


def test_create_service_returns_201(
    client: TestClient,
    auth_headers: dict[str, str]
) -> None:
    payload = {
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

    response = client.post(
        SERVICES_URL,
        json=payload,
        headers=auth_headers
        
    )

    assert response.status_code == 201

    body = response.json()

    assert body["name"] == "Orders API"
    assert body["latencyMs"] == 55


def test_negative_latency_returns_422(
    client: TestClient,
    auth_headers: dict[str, str]
) -> None:
    payload = {
        "name": "Invalid API",
        "owner": "Platform Team",
        "status": "Healthy",
        "uptime": "99.90%",
        "latencyMs": -10,
        "description": (
            "Invalid test service."
        ),
        "region": "us-east-1",
        "version": "1.0.0",
        "lastDeployedAt": (
            "2026-09-05T09:00:00Z"
        ),
        "dependencies": [],
    }

    response = client.post(
        SERVICES_URL,
        json=payload,
        headers=auth_headers
    )

    assert response.status_code == 422


def test_patch_service_updates_selected_fields(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    response = client.patch(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        json={
            "version": "2.5.0",
            "region": "us-west-2",
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert body["version"] == "2.5.0"
    assert body["region"] == "us-west-2"

    # Fields not supplied in the PATCH should remain unchanged.
    assert body["name"] == "Payments API"


def test_patch_service_updates_latency(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    response = client.patch(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        json={
            "latencyMs": 175,
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert body["latencyMs"] == 175


def test_patch_service_latency_persists(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    patch_response = client.patch(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        json={
            "latencyMs": 175,
        },
        headers=auth_headers
    )

    assert patch_response.status_code == 200

    get_response = client.get(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=auth_headers
    )

    assert get_response.status_code == 200

    body = get_response.json()

    assert body["latencyMs"] == 175


def test_delete_service_returns_204(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_services: list[Service]
) -> None:
    delete_response = client.delete(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=auth_headers
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"{SERVICES_URL}/{PAYMENTS_SERVICE_ID}",
        headers=auth_headers
    )

    assert get_response.status_code == 404
    
def test_services_require_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/services"
    )

    assert response.status_code == 401