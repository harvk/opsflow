from __future__ import annotations

from dataclasses import (
    dataclass,
)
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import (
    Protocol,
)

from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.domain.incident_task_completion_publication import (
    CompletionEventPublicationReceipt,
)
from app.messaging.sqs_incident_task_completion_publisher import (
    CompletionEventPublicationError,
)
from app.repositories.incident_task_completion_outbox_relay_repository import (
    IncidentTaskCompletionOutboxRelayRepository,
)


class IncidentTaskCompletionPublisher(
    Protocol
):
    """
    Transport boundary for publishing an already-existing
    Incident task-completion event.

    Implementations must preserve the durable event identity
    established in PostgreSQL.
    """

    def publish(
        self,
        message: IncidentTaskCompletionOutboxMessage,
    ) -> CompletionEventPublicationReceipt:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class CompletionOutboxRelayResult:
    """
    Result of one Incident task-completion outbox
    publication attempt.
    """

    outcome: str

    event_id: str | None = None

    task_id: str | None = None

    incident_id: str | None = None

    correlation_id: str | None = None

    sqs_message_id: str | None = None

    publish_attempt: int | None = None

    error: str | None = None


class IncidentTaskCompletionOutboxRelayService:
    """
    Execute one completion-event outbox publication attempt.

    Transaction commit and rollback remain owned by the
    surrounding worker process.

    SQS success marks the row PUBLISHED.

    Transport failure records the failed attempt while
    leaving the row PENDING for a future retry.
    """

    def __init__(
        self,
        *,
        repository: (
            IncidentTaskCompletionOutboxRelayRepository
        ),
        publisher: IncidentTaskCompletionPublisher,
        retry_seconds: int,
    ) -> None:
        if retry_seconds <= 0:
            raise ValueError(
                "retry_seconds must be greater than zero."
            )

        self._repository = (
            repository
        )

        self._publisher = (
            publisher
        )

        self._retry_seconds = (
            retry_seconds
        )

    def relay_once(
        self,
    ) -> CompletionOutboxRelayResult:
        now = datetime.now(
            UTC
        )

        retry_before = (
            now
            - timedelta(
                seconds=(
                    self._retry_seconds
                )
            )
        )

        record = (
            self._repository
            .lock_next_publishable(
                retry_before=(
                    retry_before
                )
            )
        )

        if record is None:
            return (
                CompletionOutboxRelayResult(
                    outcome=(
                        "no_pending_event"
                    ),
                )
            )

        message = (
            record.message
        )

        attempt_number = (
            record.publish_attempts
            + 1
        )

        try:
            receipt = (
                self._publisher
                .publish(
                    message
                )
            )

        except (
            CompletionEventPublicationError
        ) as exc:
            failed_at = datetime.now(
                UTC
            )

            (
                self._repository
                .mark_publish_failed(
                    message.id,
                    failed_at=(
                        failed_at
                    ),
                    error=str(
                        exc
                    ),
                )
            )

            return (
                CompletionOutboxRelayResult(
                    outcome=(
                        "publication_failed"
                    ),
                    event_id=str(
                        message.event_id
                    ),
                    task_id=str(
                        message.task_id
                    ),
                    incident_id=str(
                        message.incident_id
                    ),
                    correlation_id=(
                        message
                        .correlation_id
                    ),
                    publish_attempt=(
                        attempt_number
                    ),
                    error=str(
                        exc
                    ),
                )
            )

        published_at = datetime.now(
            UTC
        )

        (
            self._repository
            .mark_published(
                message.id,
                published_at=(
                    published_at
                ),
            )
        )

        return (
            CompletionOutboxRelayResult(
                outcome=(
                    "published"
                ),
                event_id=str(
                    message.event_id
                ),
                task_id=str(
                    message.task_id
                ),
                incident_id=str(
                    message.incident_id
                ),
                correlation_id=(
                    message
                    .correlation_id
                ),
                sqs_message_id=(
                    receipt.message_id
                ),
                publish_attempt=(
                    attempt_number
                ),
            )
        )
