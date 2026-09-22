from __future__ import annotations

from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class TaskAcceptedResponse(
    BaseModel
):
    """
    Public API representation of asynchronous work accepted
    for processing.

    The response intentionally exposes distributed tracing
    and idempotency identifiers without exposing transport
    details such as SQS queue URLs or AWS message IDs.
    """

    model_config = ConfigDict(
        populate_by_name=True,
    )

    status: Literal[
        "accepted"
    ] = "accepted"

    task_id: str = Field(
        alias="taskId",
    )

    task_type: str = Field(
        alias="taskType",
    )

    correlation_id: str = Field(
        alias="correlationId",
    )

    idempotency_key: str = Field(
        alias="idempotencyKey",
    )
