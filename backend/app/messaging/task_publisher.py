from __future__ import annotations

from typing import (
    Protocol,
    runtime_checkable,
)

from app.messaging.task_envelope import (
    TaskEnvelope,
)

# =========================================================
# TASK PUBLICATION ERROR
# =========================================================


class TaskPublishError(
    RuntimeError
):
    """
    Transport-independent task publication failure.

    Infrastructure implementations should translate
    transport-specific failures into this exception before
    allowing them to cross into application code.

    The task identifier is retained so callers and logs can
    correlate a publication failure with the exact envelope
    that could not be delivered.
    """

    def __init__(
        self,
        *,
        task_id: str,
        message: str = "Failed to publish task.",
    ) -> None:
        super().__init__(
            message
        )

        self.task_id = (
            task_id
        )


# =========================================================
# TASK PUBLISHER PORT
# =========================================================


@runtime_checkable
class TaskPublisher(
    Protocol
):
    """
    Application-facing port for asynchronous task delivery.

    Implementations are responsible only for delivering an
    already validated TaskEnvelope.

    Application code must not depend on the concrete
    transport used by an implementation.
    """

    def publish(
        self,
        envelope: TaskEnvelope,
    ) -> None:
        """
        Publish one validated task envelope.

        Successful completion means the transport accepted
        responsibility for the message.

        Implementations should raise TaskPublishError when
        publication fails.
        """

        ...
