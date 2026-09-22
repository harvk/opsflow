"""Handler for incident notification tasks."""

from __future__ import annotations

import json
from typing import Any


def handle_incident_notification_requested(
    task: dict[str, Any],
) -> None:
    """Handle an incident.notification.requested task.

    Phase 11.4 deliberately performs no irreversible external
    side effect. Durable idempotency is introduced in Phase 11.5.
    """

    print(
        json.dumps(
            {
                "level": "info",
                "event": "incident_notification_task_received",
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "correlation_id": task["correlation_id"],
                "idempotency_key": task["idempotency_key"],
            },
            sort_keys=True,
        )
    )