from __future__ import annotations

from pydantic import (
    JsonValue,
)

from app.messaging.task_envelope import (
    TaskEnvelope,
)
from app.messaging.task_identity import (
    DEFAULT_IDEMPOTENCY_VERSION,
    build_idempotency_key,
    resolve_correlation_id,
)
from app.messaging.task_publisher import (
    TaskPublisher,
)

# =========================================================
# TASK PUBLICATION SERVICE
# =========================================================


class TaskPublicationService:
    """
    Application-level service for constructing and
    publishing canonical OpsFlow task envelopes.

    This service owns the application-side orchestration
    required before a task reaches a transport:

        - normalize the producer identity,
        - resolve workflow correlation identity,
        - construct deterministic idempotency identity,
        - construct and validate the TaskEnvelope,
        - pass the validated envelope to TaskPublisher.

    The service deliberately has no knowledge of AWS, SQS,
    boto3, Lambda, or DynamoDB.
    """

    def __init__(
        self,
        *,
        publisher: TaskPublisher,
        producer: str,
    ) -> None:
        normalized_producer = (
            producer.strip()
        )

        if not normalized_producer:
            raise ValueError(
                "producer must not be blank."
            )

        self._publisher = (
            publisher
        )

        self._producer = (
            normalized_producer
        )

    @property
    def producer(
        self,
    ) -> str:
        """
        Return the canonical producer identity used for
        envelopes created by this service.
        """

        return self._producer

    def publish(
        self,
        *,
        task_type: str,
        scope: str,
        resource_id: str,
        operation: str,
        payload: dict[
            str,
            JsonValue,
        ],
        correlation_id: str | None = None,
        causation_id: str | None = None,
        metadata: dict[
            str,
            str,
        ]
        | None = None,
        idempotency_version: int = (
            DEFAULT_IDEMPOTENCY_VERSION
        ),
    ) -> TaskEnvelope:
        """
        Construct and publish one canonical task envelope.

        The idempotency key is derived only from stable
        business identity:

            scope
            resource_id
            operation
            semantic version

        task_id is generated independently by TaskEnvelope.

        correlation_id is preserved when supplied and
        generated when absent.

        Successful completion means TaskPublisher accepted
        the envelope. The published envelope is returned so
        callers may log or otherwise correlate the task
        identity.

        TaskPublishError is intentionally allowed to
        propagate to the application caller.
        """

        resolved_correlation_id = (
            resolve_correlation_id(
                correlation_id
            )
        )

        idempotency_key = (
            build_idempotency_key(
                scope=scope,
                resource_id=resource_id,
                operation=operation,
                version=(
                    idempotency_version
                ),
            )
        )

        envelope = TaskEnvelope(
            task_type=task_type,
            producer=(
                self._producer
            ),
            correlation_id=(
                resolved_correlation_id
            ),
            idempotency_key=(
                idempotency_key
            ),
            payload=dict(
                payload
            ),
            causation_id=(
                causation_id
            ),
            metadata=(
                {}
                if metadata is None
                else dict(
                    metadata
                )
            ),
        )

        self._publisher.publish(
            envelope
        )

        return envelope
