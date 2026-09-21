from __future__ import annotations

import json
from datetime import (
    UTC,
)
from typing import (
    Any,
)

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.domain.incident_task_publication import (
    TaskPublicationReceipt,
)


class TaskPublicationError(
    RuntimeError
):
    """
    Raised when a canonical Incident task cannot be accepted
    by Amazon SQS.
    """


class SqsIncidentTaskPublisher:
    """
    Publish existing Incident outbox identities to SQS.

    Unlike the standalone Node Task Publisher, this adapter
    does not generate task IDs, correlation IDs, timestamps,
    or idempotency keys.

    Those values already exist transactionally in PostgreSQL.
    """

    def __init__(
        self,
        *,
        queue_url: str,
        client: Any | None = None,
    ) -> None:
        resolved_queue_url = (
            queue_url.strip()
        )

        if not resolved_queue_url:
            raise ValueError(
                "queue_url must not be empty."
            )

        self._queue_url = (
            resolved_queue_url
        )

        self._client = (
            client
            if client is not None
            else boto3.client(
                "sqs"
            )
        )

    def publish(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> TaskPublicationReceipt:
        envelope = (
            self._build_envelope(
                message
            )
        )

        try:
            response = (
                self._client
                .send_message(
                    QueueUrl=(
                        self._queue_url
                    ),
                    MessageBody=(
                        json.dumps(
                            envelope,
                            separators=(
                                ",",
                                ":",
                            ),
                            sort_keys=True,
                        )
                    ),
                    MessageAttributes={
                        "task_type": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": (
                                message
                                .task_type
                            ),
                        },
                        "schema_version": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": (
                                message
                                .schema_version
                            ),
                        },
                        "correlation_id": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": (
                                message
                                .correlation_id
                            ),
                        },
                    },
                )
            )

        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise (
                TaskPublicationError(
                    "Amazon SQS task publication failed."
                )
            ) from exc

        message_id = response.get(
            "MessageId"
        )

        if (
            not isinstance(
                message_id,
                str,
            )
            or not message_id
        ):
            raise (
                TaskPublicationError(
                    "Amazon SQS did not return a MessageId."
                )
            )

        return (
            TaskPublicationReceipt(
                message_id=(
                    message_id
                )
            )
        )

    @staticmethod
    def _build_envelope(
        message: IncidentTaskOutboxMessage,
    ) -> dict[
        str,
        object,
    ]:
        created_at = (
            message
            .created_at
        )

        if created_at.tzinfo is None:
            raise (
                TaskPublicationError(
                    "Incident task created_at "
                    "must be timezone-aware."
                )
            )

        return {
            "task_id": str(
                message.task_id
            ),
            "kind": "task",
            "task_type": (
                message.task_type
            ),
            "schema_version": (
                message.schema_version
            ),
            "created_at": (
                created_at
                .astimezone(
                    UTC
                )
                .isoformat()
            ),
            "producer": (
                "incident-service"
            ),
            "correlation_id": (
                message.correlation_id
            ),
            "causation_id": (
                message.causation_id
            ),
            "idempotency_key": (
                message
                .idempotency_key
            ),
            "payload": (
                message.payload
            ),
            "metadata": (
                message.metadata
            ),
        }
