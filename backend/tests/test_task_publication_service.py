from __future__ import annotations

from uuid import (
    UUID,
)

import pytest

from app.messaging import (
    TaskEnvelope,
    TaskPublicationService,
    TaskPublishError,
)

# =========================================================
# TEST VALUES
# =========================================================

PRODUCER = (
    "opsflow-api"
)

TASK_TYPE = (
    "incident.notification.requested"
)

SCOPE = (
    "incident"
)

INCIDENT_ID = (
    "11111111-1111-4111-8111-111111111111"
)

OPERATION = (
    "notification-requested"
)

CORRELATION_ID = (
    "request:"
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
)

CAUSATION_ID = (
    "incident-created:"
    "11111111-1111-4111-8111-111111111111"
)


# =========================================================
# TEST PUBLISHERS
# =========================================================


class RecordingTaskPublisher:
    """
    In-memory publisher that records every envelope it
    receives.
    """

    def __init__(
        self,
    ) -> None:
        self.published: list[
            TaskEnvelope
        ] = []

    def publish(
        self,
        envelope: TaskEnvelope,
    ) -> None:
        self.published.append(
            envelope
        )


class FailingTaskPublisher:
    """
    Publisher that records the attempted envelope and then
    raises TaskPublishError.
    """

    def __init__(
        self,
    ) -> None:
        self.attempted: list[
            TaskEnvelope
        ] = []

    def publish(
        self,
        envelope: TaskEnvelope,
    ) -> None:
        self.attempted.append(
            envelope
        )

        raise TaskPublishError(
            task_id=(
                envelope.task_id
            ),
            message=(
                "Synthetic publication failure."
            ),
        )


# =========================================================
# TEST HELPERS
# =========================================================


def build_service(
) -> tuple[
    TaskPublicationService,
    RecordingTaskPublisher,
]:
    publisher = (
        RecordingTaskPublisher()
    )

    service = (
        TaskPublicationService(
            publisher=publisher,
            producer=PRODUCER,
        )
    )

    return (
        service,
        publisher,
    )


# =========================================================
# PRODUCER CONTRACT
# =========================================================


def test_task_publication_service_normalizes_producer(
) -> None:
    publisher = (
        RecordingTaskPublisher()
    )

    service = TaskPublicationService(
        publisher=publisher,
        producer="  opsflow-api  ",
    )

    assert (
        service.producer
        == "opsflow-api"
    )


def test_task_publication_service_rejects_blank_producer(
) -> None:
    publisher = (
        RecordingTaskPublisher()
    )

    with pytest.raises(
        ValueError,
        match=(
            "producer must not be blank"
        ),
    ):
        TaskPublicationService(
            publisher=publisher,
            producer="   ",
        )


# =========================================================
# ENVELOPE CONSTRUCTION
# =========================================================


def test_publish_constructs_and_delivers_canonical_envelope(
) -> None:
    service, publisher = (
        build_service()
    )

    envelope = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
            "customer_impacting": True,
        },
        correlation_id=(
            CORRELATION_ID
        ),
        causation_id=(
            CAUSATION_ID
        ),
        metadata={
            "source": "backend",
            "priority": "normal",
        },
    )

    assert len(
        publisher.published
    ) == 1

    assert (
        publisher.published[0]
        is envelope
    )

    assert (
        envelope.task_type
        == TASK_TYPE
    )

    assert (
        envelope.producer
        == PRODUCER
    )

    assert (
        envelope.correlation_id
        == CORRELATION_ID
    )

    assert (
        envelope.idempotency_key
        == (
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            "notification-requested:"
            "v1"
        )
    )

    assert (
        envelope.payload
        == {
            "incident_id": (
                INCIDENT_ID
            ),
            "customer_impacting": True,
        }
    )

    assert (
        envelope.causation_id
        == CAUSATION_ID
    )

    assert (
        envelope.metadata
        == {
            "source": "backend",
            "priority": "normal",
        }
    )


# =========================================================
# IDEMPOTENCY BEHAVIOR
# =========================================================


def test_same_logical_operation_reuses_idempotency_key(
) -> None:
    service, publisher = (
        build_service()
    )

    first = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
        correlation_id=(
            CORRELATION_ID
        ),
    )

    second = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
        correlation_id=(
            CORRELATION_ID
        ),
    )

    assert len(
        publisher.published
    ) == 2

    assert (
        first.idempotency_key
        == second.idempotency_key
    )

    assert (
        first.task_id
        != second.task_id
    )


def test_idempotency_version_changes_business_identity(
) -> None:
    service, _publisher = (
        build_service()
    )

    version_one = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
        correlation_id=(
            CORRELATION_ID
        ),
        idempotency_version=1,
    )

    version_two = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
        correlation_id=(
            CORRELATION_ID
        ),
        idempotency_version=2,
    )

    assert (
        version_one.idempotency_key
        != version_two.idempotency_key
    )

    assert (
        version_one.idempotency_key.endswith(
            ":v1"
        )
    )

    assert (
        version_two.idempotency_key.endswith(
            ":v2"
        )
    )


# =========================================================
# CORRELATION BEHAVIOR
# =========================================================


def test_publish_preserves_existing_correlation_id(
) -> None:
    service, _publisher = (
        build_service()
    )

    envelope = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
        correlation_id=(
            CORRELATION_ID
        ),
    )

    assert (
        envelope.correlation_id
        == CORRELATION_ID
    )


def test_publish_generates_correlation_id_when_missing(
) -> None:
    service, _publisher = (
        build_service()
    )

    envelope = service.publish(
        task_type=TASK_TYPE,
        scope=SCOPE,
        resource_id=INCIDENT_ID,
        operation=OPERATION,
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
    )

    assert (
        envelope.correlation_id.startswith(
            "corr:"
        )
    )

    generated_uuid = (
        envelope.correlation_id.removeprefix(
            "corr:"
        )
    )

    parsed_uuid = UUID(
        generated_uuid
    )

    assert (
        str(
            parsed_uuid
        )
        == generated_uuid
    )


# =========================================================
# VALIDATION BEFORE PUBLICATION
# =========================================================


def test_invalid_identity_does_not_reach_publisher(
) -> None:
    service, publisher = (
        build_service()
    )

    with pytest.raises(
        ValueError,
        match=(
            "scope must not contain"
        ),
    ):
        service.publish(
            task_type=TASK_TYPE,
            scope="incident:invalid",
            resource_id=INCIDENT_ID,
            operation=OPERATION,
            payload={
                "incident_id": (
                    INCIDENT_ID
                ),
            },
            correlation_id=(
                CORRELATION_ID
            ),
        )

    assert (
        publisher.published
        == []
    )


# =========================================================
# PUBLICATION FAILURE BEHAVIOR
# =========================================================


def test_task_publish_error_propagates_to_application_caller(
) -> None:
    publisher = (
        FailingTaskPublisher()
    )

    service = (
        TaskPublicationService(
            publisher=publisher,
            producer=PRODUCER,
        )
    )

    with pytest.raises(
        TaskPublishError,
        match=(
            "Synthetic publication failure"
        ),
    ) as exc_info:
        service.publish(
            task_type=TASK_TYPE,
            scope=SCOPE,
            resource_id=INCIDENT_ID,
            operation=OPERATION,
            payload={
                "incident_id": (
                    INCIDENT_ID
                ),
            },
            correlation_id=(
                CORRELATION_ID
            ),
        )

    assert len(
        publisher.attempted
    ) == 1

    attempted_envelope = (
        publisher.attempted[0]
    )

    assert (
        exc_info.value.task_id
        == attempted_envelope.task_id
    )

    assert (
        attempted_envelope.idempotency_key
        == (
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            "notification-requested:"
            "v1"
        )
    )
