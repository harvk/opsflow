from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from typing import (
    Annotated,
    Literal,
)
from uuid import (
    uuid4,
)

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
)

# =========================================================
# TASK CONTRACT CONSTANTS
# =========================================================

TASK_KIND: Literal[
    "task"
] = "task"

TASK_SCHEMA_VERSION: Literal[
    "1.0"
] = "1.0"


# =========================================================
# SHARED TASK STRING CONTRACT
# =========================================================

NonEmptyTaskString = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


# =========================================================
# DEFAULT VALUE FACTORIES
# =========================================================


def _new_task_id(
) -> str:
    """
    Create the unique identifier for one task-envelope
    instance.

    task_id identifies the message instance itself.

    It is intentionally separate from idempotency_key,
    which identifies the underlying logical business
    operation.
    """

    return str(
        uuid4()
    )


def _utc_now(
) -> datetime:
    """
    Return a timezone-aware UTC timestamp for a newly
    created task envelope.
    """

    return datetime.now(
        UTC
    )


# =========================================================
# TASK ENVELOPE
# =========================================================


class TaskEnvelope(
    BaseModel
):
    """
    Canonical OpsFlow asynchronous task envelope.

    This model represents the transport-independent
    message contract produced by OpsFlow applications and
    consumed by asynchronous task workers.

    The envelope deliberately distinguishes:

        task_id
            Unique identity of this individual message.

        idempotency_key
            Stable identity of the logical business
            operation represented by the message.

        correlation_id
            Identity shared by messages participating in
            the same request or workflow.

        causation_id
            Optional identity of the event/message that
            directly caused this task.

    AWS SQS is not represented in this model. SQS is only
    one possible transport for this contract.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    task_id: NonEmptyTaskString = Field(
        default_factory=_new_task_id,
    )

    kind: Literal[
        "task"
    ] = TASK_KIND

    task_type: NonEmptyTaskString

    schema_version: Literal[
        "1.0"
    ] = TASK_SCHEMA_VERSION

    created_at: AwareDatetime = Field(
        default_factory=_utc_now,
    )

    producer: NonEmptyTaskString

    correlation_id: NonEmptyTaskString

    idempotency_key: NonEmptyTaskString

    payload: dict[
        str,
        JsonValue,
    ]

    causation_id: (
        NonEmptyTaskString
        | None
    ) = None

    metadata: dict[
        str,
        str,
    ] = Field(
        default_factory=dict,
    )