from datetime import UTC, datetime
from uuid import uuid4

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
)


def test_incident_enum_values_preserve_public_contract() -> None:
    assert [
        severity.value
        for severity in IncidentSeverity
    ] == [
        "SEV-1",
        "SEV-2",
        "SEV-3",
        "SEV-4",
    ]

    assert [
        status.value
        for status in IncidentStatus
    ] == [
        "Open",
        "Investigating",
        "Monitoring",
        "Resolved",
    ]


def test_incident_create_accepts_camel_case_input() -> None:
    service_id = uuid4()
    started_at = datetime.now(UTC)

    payload = IncidentCreate.model_validate(
        {
            "title": "Elevated API latency",
            "serviceId": str(service_id),
            "severity": "SEV-2",
            "status": "Investigating",
            "summary": "Requests exceed the latency target.",
            "assignee": "Platform Operations",
            "startedAt": started_at.isoformat(),
            "source": "monitoring",
            "customerImpacting": True,
            "acknowledgedAt": started_at.isoformat(),
            "reportedByEmail": "operator@example.com",
        }
    )

    assert payload.service_id == service_id
    assert payload.severity is IncidentSeverity.SEV_2
    assert payload.status is IncidentStatus.INVESTIGATING
    assert payload.customer_impacting is True
    assert payload.source == "monitoring"
    assert payload.reported_by_email == "operator@example.com"


def test_incident_response_serializes_camel_case_contract() -> None:
    incident_id = uuid4()
    service_id = uuid4()
    timestamp = datetime.now(UTC)

    incident = Incident(
        id=incident_id,
        title="Elevated API latency",
        service_id=service_id,
        severity=IncidentSeverity.SEV_2,
        status=IncidentStatus.INVESTIGATING,
        summary="Requests exceed the latency target.",
        assignee="Platform Operations",
        source="monitoring",
        customer_impacting=True,
        acknowledged_at=timestamp,
        started_at=timestamp,
        resolved_at=None,
        created_at=timestamp,
        updated_at=timestamp,
        reported_by_email="operator@example.com",
    )

    response = IncidentResponse.model_validate(
        incident
    )

    serialized = response.model_dump(
        mode="json",
        by_alias=True,
    )

    assert serialized["id"] == str(incident_id)
    assert serialized["serviceId"] == str(service_id)
    assert serialized["severity"] == "SEV-2"
    assert serialized["status"] == "Investigating"
    assert serialized["customerImpacting"] is True
    assert serialized["reportedByEmail"] == "operator@example.com"

    expected_timestamp = (
        timestamp.isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )

    assert serialized["acknowledgedAt"] == expected_timestamp
    assert serialized["startedAt"] == expected_timestamp

    assert serialized["resolvedAt"] is None
    assert "service_id" not in serialized
    assert "customer_impacting" not in serialized