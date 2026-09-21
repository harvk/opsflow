"""Handler for Incident Processing tasks."""

from __future__ import annotations

import json
from typing import (
    Any,
)
from uuid import (
    UUID,
)

from task_worker.execution_state import (
    get_task_execution_store,
)


class InvalidIncidentProcessingTaskError(
    ValueError
):
    """
    Raised when an Incident Processing task contains an
    invalid task-specific payload.
    """


def _incident_id_from_task(
    task: dict[str, Any],
) -> str:
    """
    Extract and validate the Incident ID carried by an
    incident.processing.requested task.

    Canonical envelope validation happens before dispatch.
    This function validates the task-specific payload.
    """

    payload = task.get(
        "payload"
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise (
            InvalidIncidentProcessingTaskError(
                "Incident Processing task payload "
                "must be an object"
            )
        )

    incident_id = payload.get(
        "incident_id"
    )

    if (
        not isinstance(
            incident_id,
            str,
        )
        or not incident_id.strip()
    ):
        raise (
            InvalidIncidentProcessingTaskError(
                "Incident Processing task payload "
                "must contain a non-empty incident_id"
            )
        )

    try:
        parsed_incident_id = UUID(
            incident_id
        )

    except ValueError as exc:
        raise (
            InvalidIncidentProcessingTaskError(
                "Incident Processing task incident_id "
                "must be a valid UUID"
            )
        ) from exc

    return str(
        parsed_incident_id
    )


def handle_incident_processing_requested(
    task: dict[str, Any],
) -> None:
    """
    Persist Incident Processing execution state.

    PostgreSQL remains authoritative for Incident business
    state.

    This handler records only asynchronous execution state
    required for downstream Incident Service reconciliation.
    """

    incident_id = (
        _incident_id_from_task(
            task
        )
    )

    execution_store = (
        get_task_execution_store()
    )

    created = (
        execution_store
        .accept_incident_processing_task(
            task=task,
            incident_id=(
                incident_id
            ),
        )
    )

    event_name = (
        "incident_processing_execution_created"
        if created
        else (
            "incident_processing_execution_already_exists"
        )
    )

    print(
        json.dumps(
            {
                "level": (
                    "info"
                ),
                "event": (
                    event_name
                ),
                "task_id": task[
                    "task_id"
                ],
                "task_type": task[
                    "task_type"
                ],
                "incident_id": (
                    incident_id
                ),
                "correlation_id": task[
                    "correlation_id"
                ],
                "idempotency_key": task[
                    "idempotency_key"
                ],
                "execution_status": (
                    "READY_FOR_INCIDENT_SERVICE"
                ),
            },
            sort_keys=True,
        )
    )
