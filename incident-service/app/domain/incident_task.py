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

TASK_SCHEMA_VERSION = (
    "1.0"
)

INCIDENT_PROCESSING_TASK_TYPE = (
    "incident.processing.requested"
)


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentTaskOutboxMessage:
    """
    Durable description of an asynchronous Incident task
    waiting to be published.

    This object is publication state, not Incident business
    state and not Lambda execution state.

    PostgreSQL persists this object transactionally beside
    the Incident that caused it.

    After publication:

        SQS
            -> Lambda
            -> DynamoDB

    owns asynchronous delivery/execution concerns.
    """

    id: UUID

    task_id: UUID

    incident_id: UUID

    schema_version: str

    task_type: str

    idempotency_key: str

    correlation_id: str

    causation_id: str | None

    payload: dict[
        str,
        object,
    ]

    metadata: dict[
        str,
        str,
    ]

    created_at: datetime
