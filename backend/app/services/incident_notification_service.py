from __future__ import annotations

from typing import (
    Protocol,
)
from uuid import (
    UUID,
)

from app.domain.incident import (
    Incident,
)
from app.messaging import (
    TaskEnvelope,
    TaskPublicationService,
)

# =========================================================
# INCIDENT NOTIFICATION CONTRACT CONSTANTS
# =========================================================

INCIDENT_NOTIFICATION_TASK_TYPE = (
    "incident.notification.requested"
)

INCIDENT_NOTIFICATION_SCOPE = (
    "incident"
)

INCIDENT_NOTIFICATION_OPERATION = (
    "notification-requested"
)


# =========================================================
# INCIDENT LOOKUP PORT
# =========================================================


class IncidentLookup(
    Protocol
):
    """
    Minimal incident capability required by notification
    orchestration.

    IncidentGateway satisfies this contract structurally,
    but tests do not need to implement its unrelated CRUD
    operations.
    """

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        ...


# =========================================================
# INCIDENT NOTIFICATION SERVICE
# =========================================================


class IncidentNotificationService:
    """
    Coordinate an asynchronous notification request for an
    existing OpsFlow incident.

    This operation deliberately performs no incident
    mutation. The Incident is read first and its current
    business state becomes the task payload.

    TaskPublicationService owns envelope creation,
    correlation handling, deterministic idempotency
    identity, and transport publication.
    """

    def __init__(
        self,
        *,
        incident_lookup: IncidentLookup,
        task_publication_service: (
            TaskPublicationService
        ),
    ) -> None:
        self._incident_lookup = (
            incident_lookup
        )

        self._task_publication_service = (
            task_publication_service
        )

    def request_notification(
        self,
        *,
        incident_id: UUID,
        correlation_id: str | None,
    ) -> TaskEnvelope:
        """
        Request the canonical v1 notification operation for
        one existing Incident.

        Repeating this request for the same Incident produces
        a new task_id but the same deterministic
        idempotency_key:

            incident:<incident-id>:
            notification-requested:v1

        The downstream idempotency layer can therefore
        suppress duplicate execution.
        """

        incident = (
            self._incident_lookup
            .get_by_id(
                incident_id
            )
        )

        return (
            self._task_publication_service
            .publish(
                task_type=(
                    INCIDENT_NOTIFICATION_TASK_TYPE
                ),
                scope=(
                    INCIDENT_NOTIFICATION_SCOPE
                ),
                resource_id=str(
                    incident.id
                ),
                operation=(
                    INCIDENT_NOTIFICATION_OPERATION
                ),
                correlation_id=(
                    correlation_id
                ),
                payload={
                    "incident_id": str(
                        incident.id
                    ),
                    "service_id": str(
                        incident.service_id
                    ),
                    "title": (
                        incident.title
                    ),
                    "severity": (
                        incident.severity.value
                    ),
                    "status": (
                        incident.status.value
                    ),
                    "summary": (
                        incident.summary
                    ),
                    "assignee": (
                        incident.assignee
                    ),
                    "source": (
                        incident.source
                    ),
                    "customer_impacting": (
                        incident
                        .customer_impacting
                    ),
                },
                metadata={
                    "workflow": (
                        "incident-notification"
                    ),
                },
            )
        )
