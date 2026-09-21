from __future__ import annotations

from dataclasses import (
    dataclass,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentTaskOutboxRecord:
    """
    One durable Incident task publication obligation.

    The message contains the canonical task identity created
    transactionally beside the Incident.

    publish_attempts belongs to PostgreSQL publication state
    and is not part of the SQS task envelope.
    """

    message: IncidentTaskOutboxMessage

    publish_attempts: int


@dataclass(
    frozen=True,
    slots=True,
)
class TaskPublicationReceipt:
    """
    Transport acknowledgement returned after Amazon SQS
    accepts a task message.
    """

    message_id: str
