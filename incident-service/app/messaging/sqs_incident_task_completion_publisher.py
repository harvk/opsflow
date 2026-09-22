from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from typing import (
    Any,
)

import boto3
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.domain.incident_task_completion_publication import (
    CompletionEventPublicationReceipt,
)


class CompletionEventPublicationError(
    RuntimeError
):
    """
    Raised when an Incident task-completion event cannot be
    accepted by the realtime notification SQS queue.
    """


class SqsIncidentTaskCompletionPublisher:
    """
    Publish an existing durable Incident task-completion
    event to Amazon SQS.

    This adapter does not generate event identity.

    event_id, task_id, incident_id, correlation_id, status,
    and occurred_at were already established transactionally
    in PostgreSQL before this publisher runs.
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
        message: IncidentTaskCompletionOutboxMessage,
    ) -> CompletionEventPublicationReceipt:
        event = (
            self._build_event(
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
                            event,
                            separators=(
                                ",",
                                ":",
                            ),
                            sort_keys=True,
                        )
                    ),
                    MessageAttributes={
                        "event_type": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": (
                                message
                                .event_type
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
                        "incident_id": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": str(
                                message
                                .incident_id
                            ),
                        },
                        "task_id": {
                            "DataType": (
                                "String"
                            ),
                            "StringValue": str(
                                message
                                .task_id
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
                CompletionEventPublicationError(
                    "Amazon SQS completion-event "
                    "publication failed."
                )
            ) from exc

        message_id = (
            response.get(
                "MessageId"
            )
        )

        if (
            not isinstance(
                message_id,
                str,
            )
            or not message_id
        ):
            raise (
                CompletionEventPublicationError(
                    "Amazon SQS did not return a "
                    "MessageId for the completion event."
                )
            )

        return (
            CompletionEventPublicationReceipt(
                message_id=(
                    message_id
                )
            )
        )

    @classmethod
    def _build_event(
        cls,
        message: IncidentTaskCompletionOutboxMessage,
    ) -> dict[
        str,
        object,
    ]:
        occurred_at = (
            cls._required_aware_timestamp(
                message.occurred_at,
                field_name="occurred_at",
            )
        )

        acknowledged_at: (
            str
            | None
        ) = None

        if (
            message.acknowledged_at
            is not None
        ):
            acknowledged_at = (
                cls
                ._required_aware_timestamp(
                    message
                    .acknowledged_at,
                    field_name=(
                        "acknowledged_at"
                    ),
                )
            )

        return {
            "schema_version": (
                message.schema_version
            ),
            "event_type": (
                message.event_type
            ),
            "event_id": str(
                message.event_id
            ),
            "incident_id": str(
                message.incident_id
            ),
            "task_id": str(
                message.task_id
            ),
            "correlation_id": (
                message.correlation_id
            ),
            "status": (
                message.status.value
            ),
            "acknowledged_at": (
                acknowledged_at
            ),
            "occurred_at": (
                occurred_at
            ),
        }

    @staticmethod
    def _required_aware_timestamp(
        value: datetime,
        *,
        field_name: str,
    ) -> str:
        if value.tzinfo is None:
            raise (
                CompletionEventPublicationError(
                    "Incident task completion "
                    f"{field_name} must be "
                    "timezone-aware."
                )
            )

        return (
            value
            .astimezone(
                UTC
            )
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        )
