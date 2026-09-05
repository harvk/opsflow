from uuid import uuid4

from fastapi.testclient import TestClient

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from tests.constants import (
    PAYMENTS_INCIDENT_ID,
    PAYMENTS_SERVICE_ID,
    SECOND_INCIDENT_ID,
    THIRD_INCIDENT_ID,
)


INCIDENTS_URL = "/api/v1/incidents"

def test_service_incident_endpoint_only_returns_related_incidents(
    client,
    auth_headers: dict[str, str],
    seeded_incidents,
):
    response = client.get(
        f"/api/v1/services/{PAYMENTS_SERVICE_ID}/incidents",
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert body

    assert all(
        incident["serviceId"]
        == str(PAYMENTS_SERVICE_ID)
        for incident in body
    )
    
def test_list_incidents_for_missing_service_returns_404(
    client,
    auth_headers: dict[str, str]
):
    missing_service_id = uuid4()

    response = client.get(
        f"/api/v1/services/{missing_service_id}/incidents",
        headers=auth_headers
    )

    assert response.status_code == 404
    
def test_existing_service_with_no_incidents_returns_empty_list(
    client,
    auth_headers: dict[str, str]
):
    response = client.get(
        f"/api/v1/services/{PAYMENTS_SERVICE_ID}/incidents",
        headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == []
    
def test_service_incidents_support_pagination(
    client,
    auth_headers: dict[str, str],
    seeded_incidents,
):
    response = client.get(
        f"/api/v1/services/{PAYMENTS_SERVICE_ID}/incidents",
        params={
            "offset": 0,
            "limit": 1,
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    assert len(response.json()) <= 1
    
def test_service_incidents_reject_invalid_limit(
    client,
    auth_headers: dict[str, str]
):
    response = client.get(
        f"/api/v1/services/{PAYMENTS_SERVICE_ID}/incidents",
        params={
            "limit": 101,
        },
        headers=auth_headers
    )

    assert response.status_code == 422