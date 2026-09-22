from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from typing import (
    Any,
)
from uuid import (
    UUID,
)

import pytest

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.messaging.sqs_incident_task_publisher import (
    SqsIncidentTaskPublisher,
    TaskPublicationError,
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


class RecordingSqsClient:
    def __init__(
        self,
        *,
        message_id: (
            str
            | None
        ) = "sqs-message-123",
    ) -> None:
        self.message_id = (
            message_id
        )

        self.calls: list[
            dict[str, Any]
        ] = []

    def send_message(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(
            kwargs
        )

        if self.message_id is None:
            return {}

        return {
            "MessageId": (
                self.message_id
            ),
        }


def build_message(
) -> IncidentTaskOutboxMessage:
    return (
        IncidentTaskOutboxMessage(
            id=UUID(
                "3955e57b-f1fc-4bc5-"
                "a3b1-9f978794b365"
            ),
            task_id=TASK_ID,
            incident_id=(
                INCIDENT_ID
            ),
            schema_version="1.0",
            task_type=(
                "incident.processing.requested"
            ),
            idempotency_key=(
                "incident:"
                f"{INCIDENT_ID}:"
                "process:v1"
            ),
            correlation_id=(
                CORRELATION_ID
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
            created_at=datetime(
                2026,
                9,
                20,
                22,
                9,
                23,
                tzinfo=UTC,
            ),
        )
    )


def test_preserves_transactional_task_identity(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = (
        SqsIncidentTaskPublisher(
            queue_url=(
                "https://sqs.us-east-1.amazonaws.com/"
                "123456789012/"
                "opsflow-dev-task-queue"
            ),
            client=client,
        )
    )

    receipt = publisher.publish(
        build_message()
    )

    assert (
        receipt.message_id
        == "sqs-message-123"
    )

    assert len(
        client.calls
    ) == 1

    call = (
        client.calls[
            0
        ]
    )

    envelope = json.loads(
        call[
            "MessageBody"
        ]
    )

    assert (
        envelope[
            "task_id"
        ]
        == str(
            TASK_ID
        )
    )

    assert (
        envelope[
            "task_type"
        ]
        == (
            "incident.processing.requested"
        )
    )

    assert (
        envelope[
            "schema_version"
        ]
        == "1.0"
    )

    assert (
        envelope[
            "producer"
        ]
        == "incident-service"
    )

    assert (
        envelope[
            "correlation_id"
        ]
        == CORRELATION_ID
    )

    assert (
        envelope[
            "idempotency_key"
        ]
        == (
            "incident:"
            f"{INCIDENT_ID}:"
            "process:v1"
        )
    )

    assert (
        envelope[
            "payload"
        ]
        == {
            "incident_id": str(
                INCIDENT_ID
            ),
        }
    )

    assert (
        call[
            "MessageAttributes"
        ][
            "task_type"
        ][
            "StringValue"
        ]
        == (
            "incident.processing.requested"
        )
    )


def test_rejects_missing_sqs_message_id(
) -> None:
    client = (
        RecordingSqsClient(
            message_id=None,
        )
    )

    publisher = (
        SqsIncidentTaskPublisher(
            queue_url=(
                "https://sqs.us-east-1.amazonaws.com/"
                "123456789012/"
                "opsflow-dev-task-queue"
            ),
            client=client,
        )
    )

    with pytest.raises(
        TaskPublicationError,
        match=(
            "did not return a MessageId"
        ),
    ):
        publisher.publish(
            build_message()
        )


def test_rejects_naive_created_at(
) -> None:
    message = build_message()

    naive_message = (
        IncidentTaskOutboxMessage(
            id=message.id,
            task_id=message.task_id,
            incident_id=(
                message.incident_id
            ),
            schema_version=(
                message.schema_version
            ),
            task_type=(
                message.task_type
            ),
            idempotency_key=(
                message.idempotency_key
            ),
            correlation_id=(
                message.correlation_id
            ),
            causation_id=(
                message.causation_id
            ),
            payload=(
                message.payload
            ),
            metadata=(
                message.metadata
            ),
            created_at=(
                message
                .created_at
                .replace(
                    tzinfo=None
                )
            ),
        )
    )

    publisher = (
        SqsIncidentTaskPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=(
                RecordingSqsClient()
            ),
        )
    )

    with pytest.raises(
        TaskPublicationError,
        match=(
            "timezone-aware"
        ),
    ):
        publisher.publish(
            naive_message
        )
