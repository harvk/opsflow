from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from typing import (
    Any,
)

import pytest
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
)

from app.infrastructure.aws.sqs_task_publisher import (
    SqsTaskPublisher,
)
from app.messaging import (
    TaskEnvelope,
    TaskPublisher,
    TaskPublishError,
)

# =========================================================
# TEST VALUES
# =========================================================

QUEUE_URL = (
    "https://sqs.us-east-1.amazonaws.com/"
    "123456789012/opsflow-dev-task-queue"
)

TASK_ID = (
    "22222222-2222-4222-8222-222222222222"
)

TASK_TYPE = (
    "incident.notification.requested"
)

PRODUCER = (
    "opsflow-api"
)

CORRELATION_ID = (
    "request:test-correlation"
)

IDEMPOTENCY_KEY = (
    "incident-notification:"
    "11111111-1111-4111-8111-111111111111:"
    "created"
)

CREATED_AT = datetime(
    2026,
    9,
    19,
    2,
    0,
    0,
    tzinfo=UTC,
)


# =========================================================
# TEST CLIENTS
# =========================================================


class RecordingSqsClient:
    """
    In-memory SQS client used to record SendMessage calls.
    """

    def __init__(
        self,
    ) -> None:
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

        return {
            "MessageId": (
                "33333333-3333-4333-8333-333333333333"
            ),
        }


class FailingSqsClient:
    """
    SQS client that raises the configured exception.
    """

    def __init__(
        self,
        error: Exception,
    ) -> None:
        self._error = error

    def send_message(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        del kwargs

        raise self._error


# =========================================================
# TEST HELPERS
# =========================================================


def build_task_envelope(
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=TASK_ID,
        task_type=TASK_TYPE,
        created_at=CREATED_AT,
        producer=PRODUCER,
        correlation_id=CORRELATION_ID,
        idempotency_key=IDEMPOTENCY_KEY,
        payload={
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
            "customer_impacting": True,
            "recipients": [
                "operations",
                "support",
            ],
        },
        causation_id=(
            "incident-created:"
            "11111111-1111-4111-8111-111111111111"
        ),
        metadata={
            "source": "backend",
            "priority": "normal",
        },
    )


# =========================================================
# PUBLISHER CONTRACT
# =========================================================


def test_sqs_task_publisher_implements_task_publisher(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    assert isinstance(
        publisher,
        TaskPublisher,
    )


# =========================================================
# QUEUE CONFIGURATION
# =========================================================


def test_sqs_task_publisher_rejects_blank_queue_url(
) -> None:
    client = (
        RecordingSqsClient()
    )

    with pytest.raises(
        ValueError,
        match=(
            "queue_url must not be blank"
        ),
    ):
        SqsTaskPublisher(
            client=client,
            queue_url="   ",
        )


def test_sqs_task_publisher_normalizes_queue_url(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=(
            f"  {QUEUE_URL}  "
        ),
    )

    publisher.publish(
        build_task_envelope()
    )

    assert (
        client.calls[0]["QueueUrl"]
        == QUEUE_URL
    )


# =========================================================
# MESSAGE PUBLICATION
# =========================================================


def test_sqs_task_publisher_sends_complete_envelope(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    envelope = (
        build_task_envelope()
    )

    publisher.publish(
        envelope
    )

    assert len(
        client.calls
    ) == 1

    call = (
        client.calls[0]
    )

    assert (
        call["QueueUrl"]
        == QUEUE_URL
    )

    decoded_body = json.loads(
        call["MessageBody"]
    )

    assert (
        decoded_body
        == envelope.model_dump(
            mode="json"
        )
    )


def test_sqs_task_publisher_serializes_deterministically(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    envelope = (
        build_task_envelope()
    )

    publisher.publish(
        envelope
    )

    expected_body = json.dumps(
        envelope.model_dump(
            mode="json"
        ),
        ensure_ascii=False,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    )

    assert (
        client.calls[0]["MessageBody"]
        == expected_body
    )


def test_sqs_task_publisher_uses_only_message_body_and_queue_url(
) -> None:
    client = (
        RecordingSqsClient()
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    publisher.publish(
        build_task_envelope()
    )

    assert set(
        client.calls[0]
    ) == {
        "QueueUrl",
        "MessageBody",
    }


# =========================================================
# AWS FAILURE TRANSLATION
# =========================================================


def test_sqs_task_publisher_translates_client_error(
) -> None:
    aws_error = ClientError(
        error_response={
            "Error": {
                "Code": (
                    "AccessDeniedException"
                ),
                "Message": (
                    "Access denied."
                ),
            },
        },
        operation_name=(
            "SendMessage"
        ),
    )

    client = FailingSqsClient(
        aws_error
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    envelope = (
        build_task_envelope()
    )

    with pytest.raises(
        TaskPublishError
    ) as exc_info:
        publisher.publish(
            envelope
        )

    assert (
        exc_info.value.task_id
        == envelope.task_id
    )

    assert (
        str(
            exc_info.value
        )
        == "Failed to publish task."
    )

    assert (
        exc_info.value.__cause__
        is aws_error
    )


def test_sqs_task_publisher_translates_botocore_error(
) -> None:
    aws_error = (
        EndpointConnectionError(
            endpoint_url=QUEUE_URL,
        )
    )

    client = FailingSqsClient(
        aws_error
    )

    publisher = SqsTaskPublisher(
        client=client,
        queue_url=QUEUE_URL,
    )

    envelope = (
        build_task_envelope()
    )

    with pytest.raises(
        TaskPublishError
    ) as exc_info:
        publisher.publish(
            envelope
        )

    assert (
        exc_info.value.task_id
        == envelope.task_id
    )

    assert (
        exc_info.value.__cause__
        is aws_error
    )
