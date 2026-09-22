from __future__ import annotations

import json
from typing import (
    Any,
)

import pytest

import task_worker.handlers.incident_processing as incident_processing_module
from task_worker.handlers.incident_processing import (
    InvalidIncidentProcessingTaskError,
    handle_incident_processing_requested,
)

INCIDENT_ID = (
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)


class RecordingExecutionStore:
    def __init__(
        self,
        *,
        created: bool = True,
    ) -> None:
        self.created = (
            created
        )

        self.calls: list[
            tuple[
                dict[str, Any],
                str,
            ]
        ] = []

    def accept_incident_processing_task(
        self,
        *,
        task: dict[str, Any],
        incident_id: str,
    ) -> bool:
        self.calls.append(
            (
                task,
                incident_id,
            )
        )

        return self.created


def build_task(
    *,
    payload: object,
) -> dict[str, Any]:
    return {
        "task_id": (
            "bb587a5f-3c94-4e03-"
            "8b13-159d8f58acfa"
        ),
        "kind": "task",
        "task_type": (
            "incident.processing.requested"
        ),
        "schema_version": "1.0",
        "created_at": (
            "2026-09-20T22:09:23.315500+00:00"
        ),
        "producer": (
            "incident-service"
        ),
        "correlation_id": (
            "7385b223-c727-4297-"
            "ade2-d8089fa2d9c2"
        ),
        "causation_id": None,
        "idempotency_key": (
            "incident:"
            f"{INCIDENT_ID}:"
            "process:v1"
        ),
        "payload": (
            payload
        ),
        "metadata": {
            "source": (
                "incident-service"
            ),
            "operation": (
                "incident.create"
            ),
        },
    }


def test_persists_valid_incident_processing_task(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    execution_store = (
        RecordingExecutionStore()
    )

    monkeypatch.setattr(
        incident_processing_module,
        "get_task_execution_store",
        lambda: execution_store,
    )

    task = build_task(
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
    )

    handle_incident_processing_requested(
        task
    )

    assert (
        execution_store.calls
        == [
            (
                task,
                INCIDENT_ID,
            ),
        ]
    )

    captured = (
        capsys.readouterr()
    )

    logged_event = json.loads(
        captured.out
    )

    assert (
        logged_event[
            "event"
        ]
        == (
            "incident_processing_execution_created"
        )
    )

    assert (
        logged_event[
            "incident_id"
        ]
        == INCIDENT_ID
    )

    assert (
        logged_event[
            "execution_status"
        ]
        == (
            "READY_FOR_INCIDENT_SERVICE"
        )
    )


def test_logs_existing_execution_record(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    execution_store = (
        RecordingExecutionStore(
            created=False,
        )
    )

    monkeypatch.setattr(
        incident_processing_module,
        "get_task_execution_store",
        lambda: execution_store,
    )

    task = build_task(
        payload={
            "incident_id": (
                INCIDENT_ID
            ),
        },
    )

    handle_incident_processing_requested(
        task
    )

    captured = (
        capsys.readouterr()
    )

    logged_event = json.loads(
        captured.out
    )

    assert (
        logged_event[
            "event"
        ]
        == (
            "incident_processing_execution_"
            "already_exists"
        )
    )


def test_rejects_non_object_payload(
) -> None:
    task = build_task(
        payload=(
            "not-an-object"
        ),
    )

    with pytest.raises(
        InvalidIncidentProcessingTaskError,
        match=(
            "payload must be an object"
        ),
    ):
        handle_incident_processing_requested(
            task
        )


def test_rejects_missing_incident_id(
) -> None:
    task = build_task(
        payload={},
    )

    with pytest.raises(
        InvalidIncidentProcessingTaskError,
        match=(
            "non-empty incident_id"
        ),
    ):
        handle_incident_processing_requested(
            task
        )


def test_rejects_non_string_incident_id(
) -> None:
    task = build_task(
        payload={
            "incident_id": 12345,
        },
    )

    with pytest.raises(
        InvalidIncidentProcessingTaskError,
        match=(
            "non-empty incident_id"
        ),
    ):
        handle_incident_processing_requested(
            task
        )


def test_rejects_malformed_incident_uuid(
) -> None:
    task = build_task(
        payload={
            "incident_id": (
                "not-a-valid-uuid"
            ),
        },
    )

    with pytest.raises(
        InvalidIncidentProcessingTaskError,
        match=(
            "must be a valid UUID"
        ),
    ):
        handle_incident_processing_requested(
            task
        )
