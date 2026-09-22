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
from botocore.exceptions import (
    ClientError,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.messaging.sqs_incident_task_completion_publisher import (
    CompletionEventPublicationError,
    SqsIncidentTaskCompletionPublisher,
)

OUTBOX_ID = UUID(
    "3955e57b-f1fc-4bc5-"
    "a3b1-9f978794b365"
)

EVENT_ID = UUID(
    "7c1f9d0a-f544-47b3-"
    "b1df-642875a8fa49"
)

INCIDENT_ID = UUID(
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)

TASK_ID = UUID(
    "bb587a5f-3c94-4e03-"
    "8b13-159d8f58acfa"
)

CORRELATION_ID = (
    "7385b223-c727-4297-"
    "ade2-d8089fa2d9c2"
)

ACKNOWLEDGED_AT = datetime(
    2026,
    9,
    21,
    16,
    0,
    0,
    tzinfo=UTC,
)

OCCURRED_AT = datetime(
    2026,
    9,
    21,
    16,
    0,
    1,
    tzinfo=UTC,
)


class RecordingSqsClient:
    def __init__(
        self,
        *,
        message_id: (
            str
            | None
        ) = "completion-sqs-message-123",
        error: (
            ClientError
            | None
        ) = None,
    ) -> None:
        self.message_id = (
            message_id
        )

        self.error = (
            error
        )

        self.calls: list[
            dict[
                str,
                Any,
            ]
        ] = []

    def send_message(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        self.calls.append(
            kwargs
        )

        if self.error is not None:
            raise self.error

        if self.message_id is None:
            return {}

        return {
            "MessageId": (
                self.message_id
            ),
        }


def build_message(
    *,
    acknowledged_at: (
        datetime
        | None
    ) = ACKNOWLEDGED_AT,
    occurred_at: datetime = (
        OCCURRED_AT
    ),
) -> IncidentTaskCompletionOutboxMessage:
    return (
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
                acknowledged_at
            ),
            occurred_at=(
                occurred_at
            ),
        )
    )


def test_publishes_exact_completion_event_contract(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://sqs.us-east-1.amazonaws.com/"
                "123456789012/"
                "opsflow-dev-realtime-notification-queue"
            ),
            client=client,
        )
    )

    receipt = publisher.publish(
        build_message()
    )

    assert (
        receipt.message_id
        == "completion-sqs-message-123"
    )

    assert len(
        client.calls
    ) == 1

    call = client.calls[0]

    event = json.loads(
        call[
            "MessageBody"
        ]
    )

    assert event == {
        "schema_version": (
            "1.0"
        ),
        "event_type": (
            "incident.task.completed"
        ),
        "event_id": str(
            EVENT_ID
        ),
        "incident_id": str(
            INCIDENT_ID
        ),
        "task_id": str(
            TASK_ID
        ),
        "correlation_id": (
            CORRELATION_ID
        ),
        "status": (
            "Investigating"
        ),
        "acknowledged_at": (
            "2026-09-21T16:00:00Z"
        ),
        "occurred_at": (
            "2026-09-21T16:00:01Z"
        ),
    }

    assert set(
        event
    ) == {
        "schema_version",
        "event_type",
        "event_id",
        "incident_id",
        "task_id",
        "correlation_id",
        "status",
        "acknowledged_at",
        "occurred_at",
    }

    assert (
        call[
            "MessageAttributes"
        ][
            "event_type"
        ][
            "StringValue"
        ]
        == "incident.task.completed"
    )

    assert (
        call[
            "MessageAttributes"
        ][
            "schema_version"
        ][
            "StringValue"
        ]
        == "1.0"
    )

    assert (
        call[
            "MessageAttributes"
        ][
            "correlation_id"
        ][
            "StringValue"
        ]
        == CORRELATION_ID
    )

    assert (
        call[
            "MessageAttributes"
        ][
            "incident_id"
        ][
            "StringValue"
        ]
        == str(
            INCIDENT_ID
        )
    )

    assert (
        call[
            "MessageAttributes"
        ][
            "task_id"
        ][
            "StringValue"
        ]
        == str(
            TASK_ID
        )
    )


def test_preserves_null_acknowledgement(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=client,
        )
    )

    publisher.publish(
        build_message(
            acknowledged_at=None
        )
    )

    event = json.loads(
        client.calls[
            0
        ][
            "MessageBody"
        ]
    )

    assert (
        event[
            "acknowledged_at"
        ]
        is None
    )


def test_rejects_naive_occurred_at(
) -> None:
    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=(
                RecordingSqsClient()
            ),
        )
    )

    with pytest.raises(
        CompletionEventPublicationError,
        match=(
            "occurred_at must be timezone-aware"
        ),
    ):
        publisher.publish(
            build_message(
                occurred_at=(
                    OCCURRED_AT
                    .replace(
                        tzinfo=None
                    )
                )
            )
        )


def test_rejects_naive_acknowledged_at(
) -> None:
    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=(
                RecordingSqsClient()
            ),
        )
    )

    with pytest.raises(
        CompletionEventPublicationError,
        match=(
            "acknowledged_at must be timezone-aware"
        ),
    ):
        publisher.publish(
            build_message(
                acknowledged_at=(
                    ACKNOWLEDGED_AT
                    .replace(
                        tzinfo=None
                    )
                )
            )
        )


def test_wraps_sqs_transport_failure(
) -> None:
    client = (
        RecordingSqsClient(
            error=(
                ClientError(
                    {
                        "Error": {
                            "Code": (
                                "ServiceUnavailable"
                            ),
                            "Message": (
                                "simulated SQS failure"
                            ),
                        },
                    },
                    "SendMessage",
                )
            )
        )
    )

    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=client,
        )
    )

    with pytest.raises(
        CompletionEventPublicationError,
        match=(
            "SQS completion-event "
            "publication failed"
        ),
    ):
        publisher.publish(
            build_message()
        )


def test_rejects_missing_sqs_message_id(
) -> None:
    publisher = (
        SqsIncidentTaskCompletionPublisher(
            queue_url=(
                "https://example.invalid/queue"
            ),
            client=(
                RecordingSqsClient(
                    message_id=None
                )
            ),
        )
    )

    with pytest.raises(
        CompletionEventPublicationError,
        match=(
            "did not return a MessageId"
        ),
    ):
        publisher.publish(
            build_message()
        )
