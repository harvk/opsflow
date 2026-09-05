from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.service_repository import (
    ServiceRepository,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from app.services.exceptions import (
    IncidentNotFoundError,
    RelatedServiceNotFoundError,
)


class IncidentService:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        service_repository: ServiceRepository,
    ) -> None:
        self._incident_repository = incident_repository
        self._service_repository = service_repository

    def list_incidents(
        self,
        *,
        search: str | None = None,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        service_id: UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        return self._incident_repository.list(
            search=search,
            status=status,
            severity=severity,
            service_id=service_id,
            offset=offset,
            limit=limit,
        )

    def get_incident(
        self,
        incident_id: UUID,
    ) -> Incident:
        incident = self._incident_repository.get_by_id(incident_id)

        if incident is None:
            raise IncidentNotFoundError(f"Incident {incident_id} was not found.")

        return incident

    def create_incident(
        self,
        payload: IncidentCreate,
    ) -> Incident:
        self._validate_service_exists(payload.service_id)

        now = datetime.now(UTC)

        resolved_at = now if payload.status == IncidentStatus.RESOLVED else None

        incident = Incident(
            id=uuid4(),
            title=payload.title,
            service_id=payload.service_id,
            severity=payload.severity,
            status=payload.status,
            summary=payload.summary,
            assignee=payload.assignee,
            started_at=payload.started_at or now,
            resolved_at=resolved_at,
            created_at=now,
            updated_at=now,
        )

        return self._incident_repository.create(incident)

    def update_incident(
        self,
        incident_id: UUID,
        payload: IncidentUpdate,
    ) -> Incident:
        current_incident = self.get_incident(incident_id)

        changes = payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        new_service_id = changes.get("service_id")

        if new_service_id is not None:
            self._validate_service_exists(new_service_id)

        new_status = changes.get("status")

        now = datetime.now(UTC)

        if new_status == IncidentStatus.RESOLVED:
            if current_incident.resolved_at is None:
                changes["resolved_at"] = now

        elif new_status is not None and current_incident.status == IncidentStatus.RESOLVED:
            changes["resolved_at"] = None

        changes["updated_at"] = now

        updated_incident = replace(
            current_incident,
            **changes,
        )

        return self._incident_repository.update(updated_incident)

    def delete_incident(
        self,
        incident_id: UUID,
    ) -> None:
        self.get_incident(incident_id)

        self._incident_repository.delete(incident_id)

    def _validate_service_exists(
        self,
        service_id: UUID,
    ) -> None:
        service = self._service_repository.get_by_id(service_id)

        if service is None:
            raise RelatedServiceNotFoundError(f"Service {service_id} was not found.")
