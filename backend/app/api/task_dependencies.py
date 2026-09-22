from __future__ import annotations

from typing import (
    Annotated,
)

from fastapi import (
    Depends,
)

from app.api.dependencies import (
    IncidentGatewayDependency,
    TaskPublisherDependency,
)
from app.messaging import (
    TaskPublicationService,
)
from app.services.incident_notification_service import (
    IncidentNotificationService,
)

# =========================================================
# PRODUCER IDENTITY
# =========================================================

TASK_PRODUCER = (
    "opsflow-api"
)


# =========================================================
# TASK PUBLICATION SERVICE
# =========================================================


def get_task_publication_service(
    publisher: TaskPublisherDependency,
) -> TaskPublicationService:
    """
    Construct the application-level publication service.

    The producer identity is a stable logical service name,
    not a deployment hostname or human-readable APP_NAME.
    """

    return (
        TaskPublicationService(
            publisher=publisher,
            producer=(
                TASK_PRODUCER
            ),
        )
    )


TaskPublicationServiceDependency = (
    Annotated[
        TaskPublicationService,
        Depends(
            get_task_publication_service
        ),
    ]
)


# =========================================================
# INCIDENT NOTIFICATION SERVICE
# =========================================================


def get_incident_notification_service(
    incident_gateway: (
        IncidentGatewayDependency
    ),
    task_publication_service: (
        TaskPublicationServiceDependency
    ),
) -> IncidentNotificationService:
    return (
        IncidentNotificationService(
            incident_lookup=(
                incident_gateway
            ),
            task_publication_service=(
                task_publication_service
            ),
        )
    )


IncidentNotificationServiceDependency = (
    Annotated[
        IncidentNotificationService,
        Depends(
            get_incident_notification_service
        ),
    ]
)
