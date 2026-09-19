from __future__ import annotations

from app.messaging import (
    TaskEnvelope,
    TaskPublisher,
    TaskPublishError,
)

# =========================================================
# TEST IMPLEMENTATION
# =========================================================


class RecordingTaskPublisher:
    """
    Small in-memory publisher used to verify the structural
    TaskPublisher contract without AWS or another transport.
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


# =========================================================
# TEST HELPERS
# =========================================================


def build_task_envelope(
) -> TaskEnvelope:
    return TaskEnvelope(
        task_type=(
            "incident.notification.requested"
        ),
        producer=(
            "opsflow-api"
        ),
        correlation_id=(
            "request:test-correlation"
        ),
        idempotency_key=(
            "incident-notification:"
            "11111111-1111-4111-8111-111111111111:"
            "created"
        ),
        payload={
            "incident_id": (
                "11111111-1111-4111-8111-111111111111"
            ),
            "customer_impacting": True,
        },
    )


# =========================================================
# PROTOCOL CONTRACT
# =========================================================


def test_task_publisher_supports_structural_implementation(
) -> None:
    publisher = (
        RecordingTaskPublisher()
    )

    assert isinstance(
        publisher,
        TaskPublisher,
    )


def test_task_publisher_receives_validated_envelope(
) -> None:
    publisher = (
        RecordingTaskPublisher()
    )

    envelope = (
        build_task_envelope()
    )

    publisher.publish(
        envelope
    )

    assert (
        publisher.published
        == [
            envelope,
        ]
    )

    assert (
        publisher.published[0]
        is envelope
    )


# =========================================================
# PUBLICATION FAILURE CONTRACT
# =========================================================


def test_task_publish_error_preserves_task_id(
) -> None:
    envelope = (
        build_task_envelope()
    )

    error = TaskPublishError(
        task_id=envelope.task_id,
    )

    assert (
        error.task_id
        == envelope.task_id
    )

    assert (
        str(
            error
        )
        == "Failed to publish task."
    )


def test_task_publish_error_supports_specific_message(
) -> None:
    envelope = (
        build_task_envelope()
    )

    error = TaskPublishError(
        task_id=envelope.task_id,
        message=(
            "Task transport rejected the message."
        ),
    )

    assert (
        error.task_id
        == envelope.task_id
    )

    assert (
        str(
            error
        )
        == (
            "Task transport rejected the message."
        )
    )
