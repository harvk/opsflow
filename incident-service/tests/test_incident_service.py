from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from app.services.exceptions import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)
from app.services.incident_service import IncidentService


class InMemoryIncidentRepository:
    def __init__(
        self,
        incidents: list[Incident] | None = None,
    ) -> None:
        self.incidents = {
            incident.id: incident
            for incident in incidents or []
        }

    def list(
        self,
        *,
        search: str | None = None,
        service_id: UUID | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        incidents = list(
            self.incidents.values()
        )

        if search:
            normalized = search.strip().lower()

            incidents = [
                incident
                for incident in incidents
                if (
                    normalized in incident.title.lower()
                    or normalized in incident.summary.lower()
                    or normalized in incident.assignee.lower()
                )
            ]

        if service_id is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.service_id == service_id
            ]

        if severity is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.severity is severity
            ]

        if status is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.status is status
            ]

        incidents.sort(
            key=lambda incident: incident.created_at,
            reverse=True,
        )

        return incidents[offset : offset + limit]

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        return self.incidents.get(
            incident_id
        )

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        self.incidents[incident.id] = incident

        return incident

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        self.incidents[incident.id] = incident

        return incident

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        self.incidents.pop(
            incident_id,
            None,
        )

    def list_by_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        incidents = [
            incident
            for incident in self.incidents.values()
            if incident.service_id == service_id
        ]

        incidents.sort(
            key=lambda incident: incident.created_at,
            reverse=True,
        )

        return incidents[offset : offset + limit]


class StubServiceCatalogGateway:
    def __init__(
        self,
        existing_service_ids: set[UUID],
    ) -> None:
        self.existing_service_ids = existing_service_ids
        self.checked_service_ids: list[UUID] = []

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        self.checked_service_ids.append(
            service_id
        )

        return service_id in self.existing_service_ids


def build_incident(
    *,
    service_id: UUID,
    status: IncidentStatus = IncidentStatus.OPEN,
    resolved_at: datetime | None = None,
) -> Incident:
    timestamp = datetime.now(UTC)

    return Incident(
        id=uuid4(),
        title="Elevated API latency",
        service_id=service_id,
        severity=IncidentSeverity.SEV_2,
        status=status,
        summary="Requests exceed the latency target.",
        assignee="Platform Operations",
        source="monitoring",
        customer_impacting=False,
        acknowledged_at=None,
        started_at=timestamp,
        resolved_at=resolved_at,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_create_preserves_incident_lifecycle_fields() -> None:
    service_id = uuid4()
    acknowledged_at = datetime.now(UTC)
    repository = InMemoryIncidentRepository()
    catalog = StubServiceCatalogGateway(
        {service_id}
    )
    service = IncidentService(
        incident_repository=repository,
        service_catalog_gateway=catalog,
    )

    incident = service.create(
        IncidentCreate(
            title="Elevated API latency",
            service_id=service_id,
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.INVESTIGATING,
            summary="Requests exceed the latency target.",
            assignee="Platform Operations",
            source="monitoring",
            customer_impacting=True,
            acknowledged_at=acknowledged_at,
        )
    )

    assert incident.service_id == service_id
    assert incident.source == "monitoring"
    assert incident.customer_impacting is True
    assert incident.acknowledged_at == acknowledged_at
    assert incident.resolved_at is None
    assert catalog.checked_service_ids == [
        service_id
    ]
    assert repository.get_by_id(incident.id) == incident


def test_create_rejects_unknown_service_reference() -> None:
    service_id = uuid4()
    repository = InMemoryIncidentRepository()
    catalog = StubServiceCatalogGateway(set())
    service = IncidentService(
        incident_repository=repository,
        service_catalog_gateway=catalog,
    )

    with pytest.raises(
        IncidentServiceReferenceError,
        match=str(service_id),
    ):
        service.create(
            IncidentCreate(
                title="Elevated API latency",
                service_id=service_id,
                severity=IncidentSeverity.SEV_2,
                summary="Requests exceed the latency target.",
                assignee="Platform Operations",
            )
        )

    assert repository.incidents == {}


def test_get_by_id_rejects_unknown_incident() -> None:
    repository = InMemoryIncidentRepository()
    service = IncidentService(
        incident_repository=repository,
        service_catalog_gateway=(
            StubServiceCatalogGateway(set())
        ),
    )
    incident_id = uuid4()

    with pytest.raises(
        IncidentNotFoundError,
        match=str(incident_id),
    ):
        service.get_by_id(
            incident_id
        )


def test_update_sets_resolved_timestamp() -> None:
    service_id = uuid4()
    existing = build_incident(
        service_id=service_id
    )
    repository = InMemoryIncidentRepository(
        [existing]
    )
    service = IncidentService(
        incident_repository=repository,
        service_catalog_gateway=(
            StubServiceCatalogGateway(
                {service_id}
            )
        ),
    )

    updated = service.update(
        existing.id,
        IncidentUpdate(
            status=IncidentStatus.RESOLVED,
        ),
    )

    assert updated.status is IncidentStatus.RESOLVED
    assert updated.resolved_at is not None
    assert updated.updated_at >= existing.updated_at


def test_update_clears_timestamp_when_incident_reopens() -> None:
    service_id = uuid4()
    resolved_at = datetime.now(UTC)
    existing = build_incident(
        service_id=service_id,
        status=IncidentStatus.RESOLVED,
        resolved_at=resolved_at,
    )
    repository = InMemoryIncidentRepository(
        [existing]
    )
    service = IncidentService(
        incident_repository=repository,
        service_catalog_gateway=(
            StubServiceCatalogGateway(
                {service_id}
            )
        ),
    )

    updated = service.update(
        existing.id,
        IncidentUpdate(
            status=IncidentStatus.MONITORING,
        ),
    )

    assert updated.status is IncidentStatus.MONITORING
    assert updated.resolved_at is None


def test_list_for_service_rejects_unknown_reference() -> None:
    service_id = uuid4()
    service = IncidentService(
        incident_repository=(
            InMemoryIncidentRepository()
        ),
        service_catalog_gateway=(
            StubServiceCatalogGateway(set())
        ),
    )

    with pytest.raises(
        IncidentServiceReferenceError,
        match=str(service_id),
    ):
        service.list_for_service(
            service_id
        )