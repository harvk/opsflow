from __future__ import annotations

from typing import Any

import pytest

from task_worker.dispatcher import (
    UnsupportedTaskTypeError,
    dispatch_task,
)


def test_dispatches_registered_task_type() -> None:
    received_tasks: list[dict[str, Any]] = []

    def fake_handler(
        task: dict[str, Any],
    ) -> None:
        received_tasks.append(task)

    task = {
        "task_type": (
            "incident.notification.requested"
        ),
    }

    dispatch_task(
        task,
        handlers={
            "incident.notification.requested": (
                fake_handler
            ),
        },
    )

    assert received_tasks == [task]


def test_rejects_unregistered_task_type() -> None:
    task = {
        "task_type": "unknown.task.requested",
    }

    with pytest.raises(
        UnsupportedTaskTypeError,
        match="unknown.task.requested",
    ):
        dispatch_task(
            task,
            handlers={},
        )