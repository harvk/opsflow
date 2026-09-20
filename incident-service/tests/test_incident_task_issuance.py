from __future__ import annotations

from uuid import (
    UUID,
)

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
from app.schemas.incident import (
    IncidentCreate,
)
from app.services.incident_service import (
    IncidentService,
)

SERVICE_ID = UUID(
    "22222222-2222-4222-8222-222222222222"
)

CORRELATION_ID = (
    "incident-create-11.5g.2"
)


class RecordingIncidentRepository:
    """
    Complete in-memory IncidentRepository test double.

    The IncidentService accepts the IncidentRepository
    protocol, so this test double implements the complete
    protocol even though this particular test primarily
    exercises create().
    """

    def __init__(
        self,
    ) -> None:
        self.incidents: dict[
            UUID,
            Incident,
        ] = {}

        self.created: list[
            Incident
        ] = []

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
            normalized = (
                search
                .strip()
                .lower()
            )

            incidents = [
                incident
                for incident in incidents
                if (
                    normalized
                    in incident.title.lower()
                    or normalized
                    in incident.summary.lower()
                    or normalized
                    in incident.assignee.lower()
                )
            ]

        if service_id is not None:
            incidents = [
                incident
                for incident in incidents
                if (
                    incident.service_id
                    == service_id
                )
            ]

        if severity is not None:
            incidents = [
                incident
                for incident in incidents
                if (
                    incident.severity
                    is severity
                )
            ]

        if status is not None:
            incidents = [
                incident
                for incident in incidents
                if (
                    incident.status
                    is status
                )
            ]

        incidents.sort(
            key=(
                lambda incident:
                incident.created_at
            ),
            reverse=True,
        )

        return (
            incidents[
                offset:
                offset + limit
            ]
        )

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        return (
            self.incidents.get(
                incident_id
            )
        )

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        self.incidents[
            incident.id
        ] = incident

        self.created.append(
            incident
        )

        return incident

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        self.incidents[
            incident.id
        ] = incident

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
            for incident
            in self.incidents.values()
            if (
                incident.service_id
                == service_id
            )
        ]

        incidents.sort(
            key=(
                lambda incident:
                incident.created_at
            ),
            reverse=True,
        )

        return (
            incidents[
                offset:
                offset + limit
            ]
        )


class RecordingOutboxRepository:
    """
    In-memory IncidentTaskOutboxRepository test double.
    """

    def __init__(
        self,
    ) -> None:
        self.messages: list[
            IncidentTaskOutboxMessage
        ] = []

    def create(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> IncidentTaskOutboxMessage:
        self.messages.append(
            message
        )

        return message


class ExistingServiceCatalogGateway:
    """
    Service Catalog test double containing exactly one
    known service.
    """

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        return (
            service_id
            == SERVICE_ID
        )


def test_incident_creation_enqueues_processing_task(
) -> None:
    incident_repository = (
        RecordingIncidentRepository()
    )

    outbox_repository = (
        RecordingOutboxRepository()
    )

    service = IncidentService(
        incident_repository=(
            incident_repository
        ),
        service_catalog_gateway=(
            ExistingServiceCatalogGateway()
        ),
        incident_task_outbox_repository=(
            outbox_repository
        ),
    )

    payload = IncidentCreate(
        title=(
            "Checkout latency"
        ),
        service_id=SERVICE_ID,
        severity=(
            IncidentSeverity.SEV_2
        ),
        status=(
            IncidentStatus.INVESTIGATING
        ),
        summary=(
            "Checkout latency is elevated."
        ),
        assignee=(
            "Platform Team"
        ),
        source=(
            "monitoring"
        ),
        customer_impacting=True,
    )

    incident = service.create(
        payload,
        correlation_id=(
            CORRELATION_ID
        ),
    )

    assert len(
        incident_repository.created
    ) == 1

    assert (
        incident_repository
        .get_by_id(
            incident.id
        )
        == incident
    )

    assert len(
        outbox_repository.messages
    ) == 1

    message = (
        outbox_repository
        .messages[0]
    )

    assert (
        message.incident_id
        == incident.id
    )

    assert (
        message.schema_version
        == TASK_SCHEMA_VERSION
    )

    assert (
        message.task_type
        == INCIDENT_PROCESSING_TASK_TYPE
    )

    assert (
        message.idempotency_key
        == (
            f"incident:{incident.id}:"
            "process:v1"
        )
    )

    assert (
        message.correlation_id
        == CORRELATION_ID
    )

    assert (
        message.causation_id
        is None
    )

    assert (
        message.payload
        == {
            "incident_id": str(
                incident.id
            ),
        }
    )

    assert (
        message.metadata
        == {
            "source": (
                "incident-service"
            ),
            "operation": (
                "incident.create"
            ),
        }
    )
