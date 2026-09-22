from __future__ import annotations

from dataclasses import (
    dataclass,
)

from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentTaskCompletionOutboxRecord:
    """
    One durable Incident completion-event publication
    obligation.
    """

    message: IncidentTaskCompletionOutboxMessage

    publish_attempts: int


@dataclass(
    frozen=True,
    slots=True,
)
class CompletionEventPublicationReceipt:
    """
    Transport acknowledgement returned after Amazon SQS
    accepts an Incident task-completion event.
    """

    message_id: str
