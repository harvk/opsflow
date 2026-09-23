from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.incident_task import (
    INCIDENT_PROCESSING_TASK_TYPE,
    TASK_SCHEMA_VERSION,
    IncidentTaskOutboxMessage,
)
from app.gateways.service_catalog_gateway import (
    ServiceCatalogGateway,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.incident_task_outbox_repository import (
    IncidentTaskOutboxRepository,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from app.services.exceptions import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)


class IncidentService:
    """
    Incident Management application service.

    Business behavior is independent of FastAPI, SQLAlchemy,
    database sessions, and HTTP clients.
    """

    def __init__(
        self,
        incident_repository: IncidentRepository,
        service_catalog_gateway: ServiceCatalogGateway,
        incident_task_outbox_repository: (
            IncidentTaskOutboxRepository
        ),
    ) -> None:
        self._incident_repository = (
            incident_repository
        )

        self._service_catalog_gateway = (
            service_catalog_gateway
        )

        self._incident_task_outbox_repository = (
            incident_task_outbox_repository
        )

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
        return (
            self._incident_repository
            .list(
                search=search,
                service_id=service_id,
                severity=severity,
                status=status,
                offset=offset,
                limit=limit,
            )
        )

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        incident = (
            self._incident_repository
            .get_by_id(
                incident_id
            )
        )

        if incident is None:
            raise IncidentNotFoundError(
                f"Incident {incident_id} was not found."
            )

        return incident

    def create(
        self,
        payload: IncidentCreate,
        *,
        correlation_id: str | None = None,
    ) -> Incident:
        self._ensure_service_exists(
            payload.service_id
        )

        now = datetime.now(
            UTC
        )

        resolved_at = (
            now
            if (
                payload.status
                is IncidentStatus.RESOLVED
            )
            else None
        )

        incident = (
            Incident(
                id=uuid4(),
                title=payload.title,
                service_id=(
                    payload.service_id
                ),
                severity=(
                    payload.severity
                ),
                status=(
                    payload.status
                ),
                summary=(
                    payload.summary
                ),
                assignee=(
                    payload.assignee
                ),
                source=(
                    payload.source
                ),
                customer_impacting=(
                    payload.customer_impacting
                ),
                acknowledged_at=(
                    payload.acknowledged_at
                ),
                reported_by_email=(
                    payload.reported_by_email
                ),
                started_at=(
                    payload.started_at
                    or now
                ),
                resolved_at=(
                    resolved_at
                ),
                created_at=now,
                updated_at=now,
            )
        )

        created_incident = (
            self._incident_repository
            .create(
                incident
            )
        )

        task_id = uuid4()

        resolved_correlation_id = (
            correlation_id
            if correlation_id
            else str(
                uuid4()
            )
        )

        outbox_message = (
            IncidentTaskOutboxMessage(
                id=uuid4(),
                task_id=task_id,
                incident_id=(
                    created_incident.id
                ),
                schema_version=(
                    TASK_SCHEMA_VERSION
                ),
                task_type=(
                    INCIDENT_PROCESSING_TASK_TYPE
                ),
                idempotency_key=(
                    "incident:"
                    f"{created_incident.id}:"
                    "process:v1"
                ),
                correlation_id=(
                    resolved_correlation_id
                ),
                causation_id=None,
                payload={
                    "incident_id": str(
                        created_incident.id
                    ),
                },
                metadata={
                    "source": (
                        "incident-service"
                    ),
                    "operation": (
                        "incident.create"
                    ),
                },
                created_at=now,
            )
        )

        (
            self._incident_task_outbox_repository
            .create(
                outbox_message
            )
        )

        return created_incident

    def update(
        self,
        incident_id: UUID,
        payload: IncidentUpdate,
    ) -> Incident:
        existing = self.get_by_id(
            incident_id
        )

        if (
            payload.service_id is not None
            and payload.service_id
            != existing.service_id
        ):
            self._ensure_service_exists(
                payload.service_id
            )

        updated_status = (
            payload.status
            if payload.status is not None
            else existing.status
        )

        resolved_at = (
            self._resolve_timestamp(
                existing=existing,
                payload=payload,
                updated_status=(
                    updated_status
                ),
            )
        )

        acknowledged_at = (
            payload.acknowledged_at
            if (
                "acknowledged_at"
                in payload.model_fields_set
            )
            else existing.acknowledged_at
        )

        updated = replace(
            existing,
            title=(
                payload.title
                if payload.title
                is not None
                else existing.title
            ),
            service_id=(
                payload.service_id
                if payload.service_id
                is not None
                else existing.service_id
            ),
            severity=(
                payload.severity
                if payload.severity
                is not None
                else existing.severity
            ),
            status=updated_status,
            summary=(
                payload.summary
                if payload.summary
                is not None
                else existing.summary
            ),
            assignee=(
                payload.assignee
                if payload.assignee
                is not None
                else existing.assignee
            ),
            source=(
                payload.source
                if payload.source
                is not None
                else existing.source
            ),
            customer_impacting=(
                payload.customer_impacting
                if (
                    payload.customer_impacting
                    is not None
                )
                else (
                    existing
                    .customer_impacting
                )
            ),
            acknowledged_at=(
                acknowledged_at
            ),
            started_at=(
                payload.started_at
                if payload.started_at
                is not None
                else existing.started_at
            ),
            resolved_at=(
                resolved_at
            ),
            updated_at=(
                datetime.now(
                    UTC
                )
            ),
        )

        return (
            self._incident_repository
            .update(
                updated
            )
        )

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        self.get_by_id(
            incident_id
        )

        self._incident_repository.delete(
            incident_id
        )

    def list_for_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        self._ensure_service_exists(
            service_id
        )

        return (
            self._incident_repository
            .list_by_service(
                service_id,
                offset=offset,
                limit=limit,
            )
        )

    def _ensure_service_exists(
        self,
        service_id: UUID,
    ) -> None:
        if not (
            self._service_catalog_gateway
            .service_exists(
                service_id
            )
        ):
            raise IncidentServiceReferenceError(
                f"Service {service_id} does not exist."
            )

    @staticmethod
    def _resolve_timestamp(
        *,
        existing: Incident,
        payload: IncidentUpdate,
        updated_status: IncidentStatus,
    ) -> datetime | None:
        """
        Maintain the resolved timestamp lifecycle invariant.

        Resolved incidents receive a timestamp. Reopened
        incidents have that timestamp cleared.
        """

        if (
            updated_status
            is not IncidentStatus.RESOLVED
        ):
            return None

        if payload.resolved_at is not None:
            return payload.resolved_at

        if existing.resolved_at is not None:
            return existing.resolved_at

        return datetime.now(
            UTC
        )
