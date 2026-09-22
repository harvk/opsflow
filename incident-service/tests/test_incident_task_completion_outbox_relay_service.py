from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.domain.incident_task_completion_publication import (
    CompletionEventPublicationReceipt,
    IncidentTaskCompletionOutboxRecord,
)
from app.messaging.sqs_incident_task_completion_publisher import (
    CompletionEventPublicationError,
)
from app.services.incident_task_completion_outbox_relay_service import (
    IncidentTaskCompletionOutboxRelayService,
)

OUTBOX_ID = UUID(
    "3955e57b-f1fc-4bc5-"
    "a3b1-9f978794b365"
)

EVENT_ID = UUID(
    "7c1f9d0a-f544-47b3-"
    "b1df-642875a8fa49"
)

TASK_ID = UUID(
    "bb587a5f-3c94-4e03-"
    "8b13-159d8f58acfa"
)

INCIDENT_ID = UUID(
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)

CORRELATION_ID = (
    "7385b223-c727-4297-"
    "ade2-d8089fa2d9c2"
)


def build_record(
) -> IncidentTaskCompletionOutboxRecord:
    occurred_at = datetime.now(
        UTC
    )

    return (
        IncidentTaskCompletionOutboxRecord(
            message=(
                IncidentTaskCompletionOutboxMessage(
                    id=OUTBOX_ID,
                    event_id=EVENT_ID,
                    incident_id=(
                        INCIDENT_ID
                    ),
                    task_id=TASK_ID,
                    correlation_id=(
                        CORRELATION_ID
                    ),
                    schema_version=(
                        "1.0"
                    ),
                    event_type=(
                        "incident.task.completed"
                    ),
                    status=(
                        IncidentStatus
                        .INVESTIGATING
                    ),
                    acknowledged_at=(
                        occurred_at
                    ),
                    occurred_at=(
                        occurred_at
                    ),
                )
            ),
            publish_attempts=0,
        )
    )


class RecordingRepository:
    def __init__(
        self,
        record: (
            IncidentTaskCompletionOutboxRecord
            | None
        ),
    ) -> None:
        self.record = (
            record
        )

        self.published: list[
            UUID
        ] = []

        self.failed: list[
            UUID
        ] = []

    def lock_next_publishable(
        self,
        *,
        retry_before: datetime,
    ) -> (
        IncidentTaskCompletionOutboxRecord
        | None
    ):
        return self.record

    def mark_published(
        self,
        outbox_id: UUID,
        *,
        published_at: datetime,
    ) -> None:
        self.published.append(
            outbox_id
        )

    def mark_publish_failed(
        self,
        outbox_id: UUID,
        *,
        failed_at: datetime,
        error: str,
    ) -> None:
        self.failed.append(
            outbox_id
        )


class SuccessfulPublisher:
    def publish(
        self,
        message: IncidentTaskCompletionOutboxMessage,
    ) -> CompletionEventPublicationReceipt:
        return (
            CompletionEventPublicationReceipt(
                message_id=(
                    "completion-sqs-123"
                )
            )
        )


class FailingPublisher:
    def publish(
        self,
        message: IncidentTaskCompletionOutboxMessage,
    ) -> CompletionEventPublicationReceipt:
        raise (
            CompletionEventPublicationError(
                "simulated completion SQS failure"
            )
        )


def test_no_pending_event_is_idle(
) -> None:
    repository = (
        RecordingRepository(
            None
        )
    )

    service = (
        IncidentTaskCompletionOutboxRelayService(
            repository=repository,
            publisher=(
                SuccessfulPublisher()
            ),
            retry_seconds=15,
        )
    )

    result = (
        service.relay_once()
    )

    assert (
        result.outcome
        == "no_pending_event"
    )

    assert (
        repository.published
        == []
    )

    assert (
        repository.failed
        == []
    )


def test_success_marks_completion_event_published(
) -> None:
    record = build_record()

    repository = (
        RecordingRepository(
            record
        )
    )

    service = (
        IncidentTaskCompletionOutboxRelayService(
            repository=repository,
            publisher=(
                SuccessfulPublisher()
            ),
            retry_seconds=15,
        )
    )

    result = (
        service.relay_once()
    )

    assert (
        result.outcome
        == "published"
    )

    assert (
        result.event_id
        == str(
            EVENT_ID
        )
    )

    assert (
        result.task_id
        == str(
            TASK_ID
        )
    )

    assert (
        result.incident_id
        == str(
            INCIDENT_ID
        )
    )

    assert (
        result.correlation_id
        == CORRELATION_ID
    )

    assert (
        result.sqs_message_id
        == "completion-sqs-123"
    )

    assert (
        result.publish_attempt
        == 1
    )

    assert (
        repository.published
        == [
            OUTBOX_ID
        ]
    )

    assert (
        repository.failed
        == []
    )


def test_transport_failure_keeps_completion_event_pending(
) -> None:
    record = build_record()

    repository = (
        RecordingRepository(
            record
        )
    )

    service = (
        IncidentTaskCompletionOutboxRelayService(
            repository=repository,
            publisher=(
                FailingPublisher()
            ),
            retry_seconds=15,
        )
    )

    result = (
        service.relay_once()
    )

    assert (
        result.outcome
        == "publication_failed"
    )

    assert (
        result.event_id
        == str(
            EVENT_ID
        )
    )

    assert (
        result.publish_attempt
        == 1
    )

    assert (
        repository.failed
        == [
            OUTBOX_ID
        ]
    )

    assert (
        repository.published
        == []
    )
