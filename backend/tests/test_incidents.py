from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_incident_service,
)
from app.main import app
from app.repositories.incident_repository import (
    InMemoryIncidentRepository,
)
from app.repositories.incident_seed import (
    create_seed_incidents,
)
from app.repositories.service_repository import (
    InMemoryServiceRepository,
)
from app.repositories.service_seed import (
    create_seed_services,
)
from app.services.incident_service import (
    IncidentService,
)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    service_repository = InMemoryServiceRepository(create_seed_services())

    incident_repository = InMemoryIncidentRepository(create_seed_incidents())

    incident_service = IncidentService(
        incident_repository,
        service_repository,
    )

    app.dependency_overrides[get_incident_service] = lambda: incident_service

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_list_incidents_returns_seeded_incidents(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/incidents")

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 3

    assert "serviceId" in body[0]
    assert "startedAt" in body[0]


def test_list_incidents_can_filter_by_status(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/incidents",
        params={
            "status": "Investigating",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert body[0]["title"] == "Payment webhook processing failures"

    assert body[0]["status"] == "Investigating"


def test_list_incidents_can_filter_by_severity(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/incidents",
        params={
            "severity": "SEV-1",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["severity"] == "SEV-1"


def test_list_incidents_can_filter_by_service(
    client: TestClient,
) -> None:
    service_id = "44444444-4444-4444-8444-444444444444"

    response = client.get(
        "/api/v1/incidents",
        params={
            "serviceId": service_id,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert body[0]["serviceId"] == service_id


def test_list_incidents_can_search(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/incidents",
        params={
            "search": "inventory",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert body[0]["title"] == "Inventory synchronization latency"


def test_get_incident_returns_incident(
    client: TestClient,
) -> None:
    incident_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    response = client.get(f"/api/v1/incidents/{incident_id}")

    assert response.status_code == 200

    body = response.json()

    assert body["title"] == "Payment webhook processing failures"

    assert body["severity"] == "SEV-1"


def test_get_missing_incident_returns_404(
    client: TestClient,
) -> None:
    incident_id = "99999999-9999-4999-8999-999999999999"

    response = client.get(f"/api/v1/incidents/{incident_id}")

    assert response.status_code == 404


def test_create_incident_returns_201(
    client: TestClient,
) -> None:
    payload = {
        "title": "Order submission timeout spike",
        "serviceId": ("11111111-1111-4111-8111-111111111111"),
        "severity": "SEV-2",
        "status": "Open",
        "summary": ("Customers are experiencing elevated timeout rates while submitting orders."),
        "assignee": "Taylor Morgan",
    }

    response = client.post(
        "/api/v1/incidents",
        json=payload,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["title"] == "Order submission timeout spike"

    assert body["status"] == "Open"
    assert body["severity"] == "SEV-2"

    assert body["resolvedAt"] is None

    assert body["id"]
    assert body["createdAt"]
    assert body["updatedAt"]


def test_create_incident_with_missing_service_returns_404(
    client: TestClient,
) -> None:
    payload = {
        "title": "Unknown service outage",
        "serviceId": ("99999999-9999-4999-8999-999999999999"),
        "severity": "SEV-1",
        "summary": ("Testing invalid service references."),
        "assignee": "Platform Team",
    }

    response = client.post(
        "/api/v1/incidents",
        json=payload,
    )

    assert response.status_code == 404


def test_create_incident_with_invalid_severity_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "title": "Example incident",
        "serviceId": ("11111111-1111-4111-8111-111111111111"),
        "severity": "EXTREME",
        "summary": "Example incident summary.",
        "assignee": "Platform Team",
    }

    response = client.post(
        "/api/v1/incidents",
        json=payload,
    )

    assert response.status_code == 422


def test_resolving_incident_sets_resolved_at(
    client: TestClient,
) -> None:
    incident_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "status": "Resolved",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "Resolved"

    assert body["resolvedAt"] is not None


def test_reopening_incident_clears_resolved_at(
    client: TestClient,
) -> None:
    incident_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    first_response = client.get(f"/api/v1/incidents/{incident_id}")

    assert first_response.json()["resolvedAt"] is not None

    response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "status": "Investigating",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "Investigating"

    assert body["resolvedAt"] is None


def test_patch_incident_updates_selected_fields(
    client: TestClient,
) -> None:
    incident_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "severity": "SEV-1",
            "assignee": "Incident Commander",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["severity"] == "SEV-1"

    assert body["assignee"] == "Incident Commander"

    assert body["title"] == "Inventory synchronization latency"


def test_patch_incident_with_missing_service_returns_404(
    client: TestClient,
) -> None:
    incident_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "serviceId": ("99999999-9999-4999-8999-999999999999"),
        },
    )

    assert response.status_code == 404


def test_delete_incident_returns_204(
    client: TestClient,
) -> None:
    incident_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

    delete_response = client.delete(f"/api/v1/incidents/{incident_id}")

    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/incidents/{incident_id}")

    assert get_response.status_code == 404
