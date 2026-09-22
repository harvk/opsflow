from __future__ import annotations

from dataclasses import (
    dataclass,
)
from datetime import (
    datetime,
)
from uuid import (
    UUID,
)

from app.domain.incident import (
    IncidentStatus,
)

EVENT_SCHEMA_VERSION = (
    "1.0"
)

INCIDENT_TASK_COMPLETED_EVENT_TYPE = (
    "incident.task.completed"
)


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentTaskCompletionOutboxMessage:
    """
    Durable Incident task-completion event waiting for
    publication to the realtime notification queue.

    PostgreSQL persists this message transactionally beside
    the Incident business-state change produced by the
    reconciler.
    """

    id: UUID

    event_id: UUID

    incident_id: UUID

    task_id: UUID

    correlation_id: str

    schema_version: str

    event_type: str

    status: IncidentStatus

    acknowledged_at: (
        datetime
        | None
    )

    occurred_at: datetime
