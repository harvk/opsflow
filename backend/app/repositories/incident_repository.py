from typing import Protocol
from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


class IncidentRepository(Protocol):
    def list(
        self,
        *,
        search: str | None = None,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        service_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]: ...

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None: ...

    def create(
        self,
        incident: Incident,
    ) -> Incident: ...

    def update(
        self,
        incident: Incident,
    ) -> Incident: ...

    def delete(
        self,
        incident_id: UUID,
    ) -> None: ...


class InMemoryIncidentRepository:
    def __init__(
        self,
        initial_incidents: list[Incident] | None = None,
    ) -> None:
        self._incidents: dict[UUID, Incident] = {}

        if initial_incidents:
            for incident in initial_incidents:
                self._incidents[incident.id] = incident

    def list(
        self,
        *,
        search: str | None = None,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        service_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        incidents = list(self._incidents.values())

        if search:
            normalized_search = search.strip().lower()

            incidents = [
                incident
                for incident in incidents
                if normalized_search in incident.title.lower()
                or normalized_search in incident.summary.lower()
                or normalized_search in incident.assignee.lower()
            ]

        if status:
            incidents = [incident for incident in incidents if incident.status == status]

        if severity:
            incidents = [incident for incident in incidents if incident.severity == severity]

        if service_id:
            incidents = [incident for incident in incidents if incident.service_id == service_id]

        incidents.sort(
            key=lambda incident: incident.started_at,
            reverse=True,
        )

        return incidents[offset : offset + limit]

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        return self._incidents.get(incident_id)

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        self._incidents[incident.id] = incident

        return incident

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        self._incidents[incident.id] = incident

        return incident

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        self._incidents.pop(
            incident_id,
            None,
        )
