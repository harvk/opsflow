from __future__ import annotations

from collections.abc import (
    Generator,
)
from typing import (
    Any,
)

import pytest
from botocore.config import (
    Config,
)
from botocore.exceptions import (
    EndpointConnectionError,
)

from app.api import dependencies
from app.infrastructure.aws.sqs_task_publisher import (
    SqsTaskPublisher,
)
from app.messaging import (
    TaskEnvelope,
    TaskPublisher,
)

# =========================================================
# TEST VALUES
# =========================================================

QUEUE_URL = (
    "https://sqs.us-east-1.amazonaws.com/"
    "123456789012/opsflow-dev-task-queue"
)


# =========================================================
# TEST SQS CLIENT
# =========================================================


class RecordingSqsClient:
    """
    Deterministic no-network SQS test client.
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
                "dependency-test-message"
            ),
        }


# =========================================================
# CACHE ISOLATION
# =========================================================


@pytest.fixture(
    autouse=True
)
def clear_sqs_client_cache(
) -> Generator[
    None,
    None,
    None,
]:
    dependencies.get_sqs_client.cache_clear()

    yield

    dependencies.get_sqs_client.cache_clear()


# =========================================================
# SQS CLIENT CONSTRUCTION
# =========================================================


def test_get_sqs_client_configures_boto3_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = (
        RecordingSqsClient()
    )

    captured: dict[
        str,
        Any,
    ] = {}

    def fake_boto3_client(
        service_name: str,
        **kwargs: Any,
    ) -> RecordingSqsClient:
        captured[
            "service_name"
        ] = service_name

        captured.update(
            kwargs
        )

        return fake_client

    monkeypatch.setattr(
        dependencies
        .boto3,
        "client",
        fake_boto3_client,
    )

    client = (
        dependencies
        .get_sqs_client()
    )

    assert (
        client
        is fake_client
    )

    assert (
        captured[
            "service_name"
        ]
        == "sqs"
    )

    assert (
        captured[
            "region_name"
        ]
        == dependencies.settings.aws_region
    )

    aws_config = (
        captured[
            "config"
        ]
    )

    assert isinstance(
        aws_config,
        Config,
    )

    assert (
        getattr(
            aws_config,
            "connect_timeout",
        )
        == 3
    )

    assert (
        getattr(
            aws_config,
            "read_timeout",
        )
        == 5
    )

    retries = getattr(
        aws_config,
        "retries",
    )

    assert (
        retries[
            "mode"
        ]
        == "standard"
    )

    assert (
        retries[
            "total_max_attempts"
        ]
        == 3
    )


def test_get_sqs_client_is_process_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = (
        RecordingSqsClient()
    )

    call_count = 0

    def fake_boto3_client(
        service_name: str,
        **kwargs: Any,
    ) -> RecordingSqsClient:
        nonlocal call_count

        del service_name
        del kwargs

        call_count += 1

        return fake_client

    monkeypatch.setattr(
        dependencies
        .boto3,
        "client",
        fake_boto3_client,
    )

    first = (
        dependencies
        .get_sqs_client()
    )

    second = (
        dependencies
        .get_sqs_client()
    )

    assert (
        first
        is second
    )

    assert (
        call_count
        == 1
    )


def test_get_sqs_client_translates_construction_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    aws_error = (
        EndpointConnectionError(
            endpoint_url=(
                "https://sqs.us-east-1.amazonaws.com"
            ),
        )
    )

    def failing_boto3_client(
        service_name: str,
        **kwargs: Any,
    ) -> RecordingSqsClient:
        del service_name
        del kwargs

        raise aws_error

    monkeypatch.setattr(
        dependencies
        .boto3,
        "client",
        failing_boto3_client,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Task publisher is unavailable"
        ),
    ) as exc_info:
        dependencies.get_sqs_client()

    assert (
        exc_info.value.__cause__
        is aws_error
    )


# =========================================================
# TASK PUBLISHER CONSTRUCTION
# =========================================================


def test_get_task_publisher_builds_sqs_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = (
        RecordingSqsClient()
    )

    monkeypatch.setattr(
        dependencies.settings,
        "task_queue_url",
        QUEUE_URL,
    )

    publisher = (
        dependencies
        .get_task_publisher(
            client
        )
    )

    assert isinstance(
        publisher,
        TaskPublisher,
    )

    assert isinstance(
        publisher,
        SqsTaskPublisher,
    )

    envelope = TaskEnvelope(
        task_type=(
            "incident.notification.requested"
        ),
        producer=(
            "opsflow-api"
        ),
        correlation_id=(
            "request:dependency-test"
        ),
        idempotency_key=(
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            "notification"
        ),
        payload={
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
        },
    )

    publisher.publish(
        envelope
    )

    assert len(
        client.calls
    ) == 1

    assert (
        client.calls[0][
            "QueueUrl"
        ]
        == QUEUE_URL
    )


def test_get_task_publisher_requires_queue_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = (
        RecordingSqsClient()
    )

    monkeypatch.setattr(
        dependencies.settings,
        "task_queue_url",
        None,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "TASK_QUEUE_URL must be configured"
        ),
    ):
        dependencies.get_task_publisher(
            client
        )
