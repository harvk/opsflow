from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)


def build_incident(
    *,
    service_id: UUID,
    title: str = "Elevated API latency",
    severity: IncidentSeverity = IncidentSeverity.SEV_2,
    status: IncidentStatus = IncidentStatus.OPEN,
) -> Incident:
    timestamp = datetime.now(UTC)

    return Incident(
        id=uuid4(),
        service_id=service_id,
        title=title,
        severity=severity,
        status=status,
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


def test_create_and_get_round_trip(
    db_session: Session,
) -> None:
    repository = SqlAlchemyIncidentRepository(
        db_session
    )
    incident = build_incident(
        service_id=uuid4()
    )

    created = repository.create(
        incident
    )
    loaded = repository.get_by_id(
        incident.id
    )

    assert created == incident
    assert loaded == incident


def test_list_applies_incident_filters(
    db_session: Session,
) -> None:
    repository = SqlAlchemyIncidentRepository(
        db_session
    )
    payments_service_id = uuid4()
    search_target = build_incident(
        service_id=payments_service_id,
        title="Payments latency alert",
        severity=IncidentSeverity.SEV_1,
        status=IncidentStatus.INVESTIGATING,
    )
    unrelated = build_incident(
        service_id=uuid4(),
        title="Unrelated monitoring alert",
        severity=IncidentSeverity.SEV_3,
        status=IncidentStatus.MONITORING,
    )

    repository.create(
        search_target
    )
    repository.create(
        unrelated
    )

    results = repository.list(
        search="payments",
        service_id=payments_service_id,
        severity=IncidentSeverity.SEV_1,
        status=IncidentStatus.INVESTIGATING,
    )

    assert results == [
        search_target
    ]


def test_update_round_trip(
    db_session: Session,
) -> None:
    repository = SqlAlchemyIncidentRepository(
        db_session
    )
    incident = build_incident(
        service_id=uuid4()
    )
    repository.create(
        incident
    )

    resolved_at = datetime.now(UTC)
    updated = replace(
        incident,
        status=IncidentStatus.RESOLVED,
        summary="Latency returned to normal.",
        customer_impacting=False,
        resolved_at=resolved_at,
        updated_at=resolved_at,
    )

    persisted = repository.update(
        updated
    )
    loaded = repository.get_by_id(
        incident.id
    )

    assert persisted == updated
    assert loaded == updated


def test_delete_removes_incident(
    db_session: Session,
) -> None:
    repository = SqlAlchemyIncidentRepository(
        db_session
    )
    incident = build_incident(
        service_id=uuid4()
    )
    repository.create(
        incident
    )

    repository.delete(
        incident.id
    )

    assert repository.get_by_id(
        incident.id
    ) is None