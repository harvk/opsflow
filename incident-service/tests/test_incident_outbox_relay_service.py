from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.domain.incident_task_publication import (
    IncidentTaskOutboxRecord,
    TaskPublicationReceipt,
)
from app.messaging.sqs_incident_task_publisher import (
    TaskPublicationError,
)
from app.services.incident_outbox_relay_service import (
    IncidentOutboxRelayService,
)

OUTBOX_ID = UUID(
    "3955e57b-f1fc-4bc5-"
    "a3b1-9f978794b365"
)

TASK_ID = UUID(
    "bb587a5f-3c94-4e03-"
    "8b13-159d8f58acfa"
)

INCIDENT_ID = UUID(
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)


def build_record(
) -> IncidentTaskOutboxRecord:
    return (
        IncidentTaskOutboxRecord(
            message=(
                IncidentTaskOutboxMessage(
                    id=OUTBOX_ID,
                    task_id=TASK_ID,
                    incident_id=(
                        INCIDENT_ID
                    ),
                    schema_version=(
                        "1.0"
                    ),
                    task_type=(
                        "incident.processing.requested"
                    ),
                    idempotency_key=(
                        "incident:"
                        f"{INCIDENT_ID}:"
                        "process:v1"
                    ),
                    correlation_id=(
                        "7385b223-c727-4297-"
                        "ade2-d8089fa2d9c2"
                    ),
                    causation_id=None,
                    payload={
                        "incident_id": str(
                            INCIDENT_ID
                        ),
                    },
                    metadata={
                        "source": (
                            "incident-service"
                        ),
                        "operation": (
                            "incident.create"
                        ),
                    },
                    created_at=datetime.now(
                        UTC
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
            IncidentTaskOutboxRecord
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
        IncidentTaskOutboxRecord
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
        message: IncidentTaskOutboxMessage,
    ) -> TaskPublicationReceipt:
        return (
            TaskPublicationReceipt(
                message_id=(
                    "sqs-message-123"
                )
            )
        )


class FailingPublisher:
    def publish(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> TaskPublicationReceipt:
        raise TaskPublicationError(
            "simulated SQS failure"
        )


def test_no_pending_task_is_idle(
) -> None:
    repository = (
        RecordingRepository(
            None
        )
    )

    service = (
        IncidentOutboxRelayService(
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
        == "no_pending_task"
    )

    assert (
        repository.published
        == []
    )


def test_success_marks_outbox_published(
) -> None:
    record = build_record()

    repository = (
        RecordingRepository(
            record
        )
    )

    service = (
        IncidentOutboxRelayService(
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
        result.task_id
        == str(
            TASK_ID
        )
    )

    assert (
        result.sqs_message_id
        == "sqs-message-123"
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


def test_transport_failure_keeps_task_pending(
) -> None:
    record = build_record()

    repository = (
        RecordingRepository(
            record
        )
    )

    service = (
        IncidentOutboxRelayService(
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
        repository.failed
        == [
            OUTBOX_ID
        ]
    )

    assert (
        repository.published
        == []
    )
