from __future__ import annotations

import json
from typing import (
    Any,
    Protocol,
)

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from app.messaging import (
    TaskEnvelope,
    TaskPublishError,
)

# =========================================================
# SQS CLIENT CONTRACT
# =========================================================


class SqsClient(
    Protocol
):
    """
    Minimal SQS client surface required by the task
    publisher.

    This deliberately avoids coupling the application to a
    generated boto3 client type or boto3-stubs package.
    """

    def send_message(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        ...


# =========================================================
# SQS TASK PUBLISHER
# =========================================================


class SqsTaskPublisher:
    """
    AWS SQS implementation of the TaskPublisher port.

    The publisher accepts an already validated TaskEnvelope,
    serializes the canonical v1 contract to deterministic
    JSON, and submits the resulting message body to the
    configured SQS queue.

    AWS-specific failures are translated into
    TaskPublishError before crossing the infrastructure
    boundary.
    """

    def __init__(
        self,
        *,
        client: SqsClient,
        queue_url: str,
    ) -> None:
        normalized_queue_url = (
            queue_url.strip()
        )

        if not normalized_queue_url:
            raise ValueError(
                "queue_url must not be blank."
            )

        self._client = client
        self._queue_url = (
            normalized_queue_url
        )

    @staticmethod
    def _serialize_envelope(
        envelope: TaskEnvelope,
    ) -> str:
        """
        Serialize a task envelope into deterministic,
        compact JSON suitable for an SQS message body.
        """

        return json.dumps(
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

    def publish(
        self,
        envelope: TaskEnvelope,
    ) -> None:
        """
        Publish one canonical task envelope to SQS.

        Successful return means the SQS SendMessage request
        completed successfully.

        Botocore/AWS client failures are translated into the
        transport-independent TaskPublishError contract.
        """

        message_body = (
            self._serialize_envelope(
                envelope
            )
        )

        try:
            self._client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=message_body,
            )
        except (
            BotoCoreError,
            ClientError,
        ) as exc:
            raise TaskPublishError(
                task_id=envelope.task_id,
            ) from exc
