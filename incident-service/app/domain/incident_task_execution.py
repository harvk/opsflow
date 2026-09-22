from __future__ import annotations

from dataclasses import (
    dataclass,
)
from enum import (
    Enum,
)
from uuid import (
    UUID,
)


class IncidentTaskExecutionStatus(
    str,
    Enum,
):
    """
    Lifecycle states for asynchronous Incident task
    reconciliation.

    These are execution states, not Incident business
    lifecycle states.
    """

    READY_FOR_INCIDENT_SERVICE = (
        "READY_FOR_INCIDENT_SERVICE"
    )

    INCIDENT_SERVICE_PROCESSING = (
        "INCIDENT_SERVICE_PROCESSING"
    )

    SUCCEEDED = (
        "SUCCEEDED"
    )

    FAILED = (
        "FAILED"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentTaskExecution:
    """
    DynamoDB-backed asynchronous execution record.

    PostgreSQL remains authoritative for the Incident itself.
    """

    task_id: str

    incident_id: UUID

    task_type: str

    correlation_id: str

    created_at: str

    status: IncidentTaskExecutionStatus

    reconciliation_attempts: int

    lease_expires_at: int | None = None

    reconciliation_token: str | None = None
