from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


class InMemoryIncidentRepository:
    def __init__(self) -> None:
        self._incidents: dict[UUID, Incident] = {}

    def list(
        self,
        *,
        search: str | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        incidents = list(self._incidents.values())

        if search:
            search_value = search.strip().lower()

            incidents = [
                incident
                for incident in incidents
                if (
                    search_value in incident.title.lower()
                    or search_value in incident.summary.lower()
                    or search_value in incident.assignee.lower()
                )
            ]

        if severity is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.severity == severity
            ]

        if status is not None:
            incidents = [
                incident
                for incident in incidents
                if incident.status == status
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
        if incident.id not in self._incidents:
            raise LookupError(
                f"Incident {incident.id} does not exist."
            )

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