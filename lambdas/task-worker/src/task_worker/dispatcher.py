"""Dispatch validated OpsFlow tasks to task-specific handlers."""

from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from typing import Any

from task_worker.handlers.incident_notification import (
    handle_incident_notification_requested,
)
from task_worker.handlers.incident_processing import (
    handle_incident_processing_requested,
)

TaskHandler = Callable[
    [
        dict[str, Any]
    ],
    None,
]


class UnsupportedTaskTypeError(
    ValueError
):
    """
    Raised when no worker handler exists for a task type.
    """


TASK_HANDLERS: dict[
    str,
    TaskHandler,
] = {
    "incident.notification.requested": (
        handle_incident_notification_requested
    ),
    "incident.processing.requested": (
        handle_incident_processing_requested
    ),
}


def dispatch_task(
    task: dict[str, Any],
    handlers: Mapping[
        str,
        TaskHandler,
    ]
    | None = None,
) -> None:
    """
    Dispatch a validated task to its registered handler.
    """

    configured_handlers = (
        handlers
        if handlers is not None
        else TASK_HANDLERS
    )

    task_type = task[
        "task_type"
    ]

    handler = (
        configured_handlers.get(
            task_type
        )
    )

    if handler is None:
        raise UnsupportedTaskTypeError(
            "Unsupported task type: "
            f"{task_type}"
        )

    handler(
        task
    )
