from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def test_list_incidents_returns_seeded_incidents(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        INCIDENTS_URL,
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert isinstance(body, list)
    assert len(body) == 3

    returned_ids = {
        incident["id"]
        for incident in body
    }

    assert str(PAYMENTS_INCIDENT_ID) in returned_ids
    assert str(SECOND_INCIDENT_ID) in returned_ids
    assert str(THIRD_INCIDENT_ID) in returned_ids


def test_list_incidents_can_filter_by_status(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        INCIDENTS_URL,
        params={
            "status": (
                IncidentStatus.INVESTIGATING.value
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert (
        body[0]["status"]
        == IncidentStatus.INVESTIGATING.value
    )


def test_list_incidents_can_filter_by_severity(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        INCIDENTS_URL,
        params={
            "severity": (
                IncidentSeverity.SEV_1.value
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert (
        body[0]["severity"]
        == IncidentSeverity.SEV_1.value
    )


def test_list_incidents_can_filter_by_service(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        INCIDENTS_URL,
        params={
            "serviceId": str(
                PAYMENTS_SERVICE_ID
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    # Our current seeded fixture places all three
    # incidents under Payments API.
    assert len(body) == 3

    for incident in body:
        assert (
            incident["serviceId"]
            == str(PAYMENTS_SERVICE_ID)
        )


def test_list_incidents_can_search(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        INCIDENTS_URL,
        params={
            "search": "error spike",
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1

    assert (
        body[0]["id"]
        == str(SECOND_INCIDENT_ID)
    )

    assert (
        body[0]["title"]
        == "Payment error spike"
    )


def test_get_incident_returns_incident(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.get(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        headers=auth_headers
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["id"]
        == str(PAYMENTS_INCIDENT_ID)
    )

    assert (
        body["serviceId"]
        == str(PAYMENTS_SERVICE_ID)
    )

    assert (
        body["title"]
        == "Elevated payment latency"
    )

    assert (
        body["severity"]
        == IncidentSeverity.SEV_2.value
    )

    assert (
        body["status"]
        == IncidentStatus.INVESTIGATING.value
    )


def test_create_incident_returns_201(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
) -> None:
    payload = {
        "title": "Payments API errors",
        "serviceId": str(
            PAYMENTS_SERVICE_ID
        ),
        "severity": (
            IncidentSeverity.SEV_2.value
        ),
        "status": (
            IncidentStatus.INVESTIGATING.value
        ),
        "summary": (
            "An elevated error rate "
            "was detected."
        ),
        "assignee": "Payments Team",
    }

    response = client.post(
        INCIDENTS_URL,
        json=payload,
        headers=auth_headers
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert (
        body["title"]
        == "Payments API errors"
    )

    assert (
        body["serviceId"]
        == str(PAYMENTS_SERVICE_ID)
    )

    assert (
        body["severity"]
        == IncidentSeverity.SEV_2.value
    )

    assert (
        body["status"]
        == IncidentStatus.INVESTIGATING.value
    )

    assert body["id"] is not None
    assert body["createdAt"] is not None
    assert body["updatedAt"] is not None


def test_create_incident_with_missing_service_returns_404(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    missing_service_id = uuid4()

    payload = {
        "title": "Unknown service incident",
        "serviceId": str(
            missing_service_id
        ),
        "severity": (
            IncidentSeverity.SEV_2.value
        ),
        "status": (
            IncidentStatus.INVESTIGATING.value
        ),
        "summary": (
            "This Incident references a "
            "Service that does not exist."
        ),
        "assignee": "Platform Team",
    }

    response = client.post(
        INCIDENTS_URL,
        json=payload,
        headers=auth_headers
    )

    assert response.status_code == 404, response.text


def test_resolving_incident_sets_resolved_at(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.patch(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        json={
            "status": (
                IncidentStatus.RESOLVED.value
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert (
        body["status"]
        == IncidentStatus.RESOLVED.value
    )

    assert body["resolvedAt"] is not None


def test_reopening_incident_clears_resolved_at(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    # THIRD_INCIDENT_ID is seeded as Resolved.
    before_response = client.get(
        f"{INCIDENTS_URL}/{THIRD_INCIDENT_ID}",
        headers=auth_headers
    )

    assert before_response.status_code == 200

    before_body = before_response.json()

    assert (
        before_body["status"]
        == IncidentStatus.RESOLVED.value
    )

    assert before_body["resolvedAt"] is not None

    response = client.patch(
        f"{INCIDENTS_URL}/{THIRD_INCIDENT_ID}",
        json={
            "status": (
                IncidentStatus.INVESTIGATING.value
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert (
        body["status"]
        == IncidentStatus.INVESTIGATING.value
    )

    assert body["resolvedAt"] is None


def test_patch_incident_updates_selected_fields(
    client: TestClient,
    db_session: Session,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    response = client.patch(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        json={
            "assignee": "Platform Team",
            "severity": (
                IncidentSeverity.SEV_1.value
            ),
        },
        headers=auth_headers
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert (
        body["assignee"]
        == "Platform Team"
    )

    assert (
        body["severity"]
        == IncidentSeverity.SEV_1.value
    )

    # Fields not included in the PATCH
    # should remain unchanged.
    assert (
        body["title"]
        == "Elevated payment latency"
    )

    assert (
        body["serviceId"]
        == str(PAYMENTS_SERVICE_ID)
    )


def test_patch_incident_changes_persist(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    patch_response = client.patch(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        json={
            "assignee": "SRE Team",
        },
        headers=auth_headers
    )

    assert (
        patch_response.status_code
        == 200
    ), patch_response.text

    get_response = client.get(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        headers=auth_headers
    )

    assert get_response.status_code == 200

    body = get_response.json()

    assert body["assignee"] == "SRE Team"


def test_delete_incident_returns_204(
    client: TestClient,
    auth_headers: dict[str, str],
    seeded_incidents: list[Incident],
) -> None:
    delete_response = client.delete(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        headers=auth_headers
    )

    assert (
        delete_response.status_code
        == 204
    ), delete_response.text

    get_response = client.get(
        f"{INCIDENTS_URL}/{PAYMENTS_INCIDENT_ID}",
        headers=auth_headers
    )

    assert get_response.status_code == 404
    
def test_incidents_require_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/incidents"
    )

    assert response.status_code == 401