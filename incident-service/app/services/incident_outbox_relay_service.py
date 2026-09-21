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

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.domain.incident_task_publication import (
    TaskPublicationReceipt,
)
from app.messaging.sqs_incident_task_publisher import (
    TaskPublicationError,
)
from app.repositories.incident_task_outbox_relay_repository import (
    IncidentTaskOutboxRelayRepository,
)


class IncidentTaskPublisher(
    Protocol
):
    """
    Transport boundary for publishing an existing canonical
    Incident task.

    Implementations must preserve the task identity already
    established transactionally in PostgreSQL.
    """

    def publish(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> TaskPublicationReceipt:
        ...


@dataclass(
    frozen=True,
    slots=True,
)
class OutboxRelayResult:
    """
    Result of one transactional outbox publication attempt.
    """

    outcome: str

    task_id: str | None = None

    correlation_id: str | None = None

    sqs_message_id: str | None = None

    publish_attempt: int | None = None

    error: str | None = None


class IncidentOutboxRelayService:
    """
    Execute one PostgreSQL outbox publication attempt.

    Transaction commit and rollback are owned by the
    surrounding relay worker process.
    """

    def __init__(
        self,
        *,
        repository: (
            IncidentTaskOutboxRelayRepository
        ),
        publisher: IncidentTaskPublisher,
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
    ) -> OutboxRelayResult:
        """
        Attempt publication of one eligible outbox record.

        Successful SQS acknowledgement marks the PostgreSQL
        outbox row PUBLISHED.

        A transport failure records the failed attempt while
        leaving the row PENDING for a future retry.
        """

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
                OutboxRelayResult(
                    outcome=(
                        "no_pending_task"
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

        except TaskPublicationError as exc:
            failed_at = (
                datetime.now(
                    UTC
                )
            )

            self._repository.mark_publish_failed(
                message.id,
                failed_at=(
                    failed_at
                ),
                error=str(
                    exc
                ),
            )

            return (
                OutboxRelayResult(
                    outcome=(
                        "publication_failed"
                    ),
                    task_id=str(
                        message.task_id
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

        published_at = (
            datetime.now(
                UTC
            )
        )

        self._repository.mark_published(
            message.id,
            published_at=(
                published_at
            ),
        )

        return (
            OutboxRelayResult(
                outcome=(
                    "published"
                ),
                task_id=str(
                    message.task_id
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
