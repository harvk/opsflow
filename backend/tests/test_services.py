from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_service_service
from app.main import app
from app.repositories.service_repository import (
    InMemoryServiceRepository,
)
from app.repositories.service_seed import (
    create_seed_services,
)
from app.services.service_service import (
    ServiceService,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    repository = InMemoryServiceRepository(create_seed_services())

    service_service = ServiceService(repository)

    app.dependency_overrides[get_service_service] = lambda: service_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_list_services_returns_seeded_services(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/services")

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 4

    assert "latencyMs" in body[0]


def test_list_services_can_filter_by_status(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/services",
        params={"status": "Critical"},
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["name"] == "Payment Webhook"
    assert body[0]["status"] == "Critical"


def test_get_service_returns_service(
    client: TestClient,
) -> None:
    service_id = "11111111-1111-4111-8111-111111111111"

    response = client.get(f"/api/v1/services/{service_id}")

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "Order API"
    assert body["latencyMs"] == 42


def test_get_missing_service_returns_404(
    client: TestClient,
) -> None:
    service_id = "99999999-9999-4999-8999-999999999999"

    response = client.get(f"/api/v1/services/{service_id}")

    assert response.status_code == 404


def test_create_service_returns_201(
    client: TestClient,
) -> None:
    payload = {
        "name": "Billing API",
        "owner": "Finance Platform",
        "status": "Healthy",
        "uptime": "99.98%",
        "latencyMs": 55,
        "description": "Handles billing workflows.",
        "region": "us-east-1",
        "version": "1.0.0",
        "dependencies": ["Payment Webhook"],
    }

    response = client.post(
        "/api/v1/services",
        json=payload,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["name"] == "Billing API"
    assert body["latencyMs"] == 55
    assert body["id"]


def test_create_duplicate_service_returns_409(
    client: TestClient,
) -> None:
    payload = {
        "name": "Order API",
        "owner": "Another Team",
    }

    response = client.post(
        "/api/v1/services",
        json=payload,
    )

    assert response.status_code == 409


def test_negative_latency_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "name": "Broken API",
        "owner": "Platform",
        "latencyMs": -1,
    }

    response = client.post(
        "/api/v1/services",
        json=payload,
    )

    assert response.status_code == 422


def test_patch_service_updates_selected_fields(
    client: TestClient,
) -> None:
    service_id = "11111111-1111-4111-8111-111111111111"

    response = client.patch(
        f"/api/v1/services/{service_id}",
        json={
            "status": "Degraded",
            "latencyMs": 250,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "Order API"
    assert body["status"] == "Degraded"
    assert body["latencyMs"] == 250


def test_delete_service_returns_204(
    client: TestClient,
) -> None:
    service_id = "11111111-1111-4111-8111-111111111111"

    delete_response = client.delete(f"/api/v1/services/{service_id}")

    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/services/{service_id}")

    assert get_response.status_code == 404
