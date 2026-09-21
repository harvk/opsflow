from __future__ import annotations

import copy
import json
from collections.abc import (
    Callable,
)
from pathlib import (
    Path,
)
from typing import (
    Any,
)

import pytest

import task_worker.handler as handler_module
import task_worker.handlers.incident_processing as incident_processing_module
from task_worker.handler import (
    lambda_handler,
)

REPOSITORY_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

VALID_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "tasks"
    / "fixtures"
    / "valid-task-v1.json"
)

TaskProcessor = Callable[
    [
        dict[str, Any]
    ],
    None,
]


INCIDENT_ID = (
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)


class FakeExecutionStore:
    def accept_incident_processing_task(
        self,
        *,
        task: dict[str, Any],
        incident_id: str,
    ) -> bool:
        assert (
            task[
                "task_type"
            ]
            == (
                "incident.processing.requested"
            )
        )

        assert (
            incident_id
            == INCIDENT_ID
        )

        return True


@pytest.fixture(
    autouse=True,
)
def bypass_external_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Keep handler unit tests independent from DynamoDB.

    Powertools persistence and Incident execution-state
    persistence are tested separately.
    """

    def register_context_directly(
        _context: Any,
    ) -> None:
        return None

    def process_directly(
        *,
        task: dict[str, Any],
        processor: TaskProcessor,
    ) -> None:
        processor(
            task
        )

    monkeypatch.setattr(
        handler_module,
        "register_lambda_context",
        register_context_directly,
    )

    monkeypatch.setattr(
        handler_module,
        "process_task_idempotently",
        process_directly,
    )

    monkeypatch.setattr(
        incident_processing_module,
        "get_task_execution_store",
        lambda: (
            FakeExecutionStore()
        ),
    )


def load_valid_task(
) -> dict[str, Any]:
    with VALID_FIXTURE_PATH.open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        return json.load(
            fixture_file
        )


def create_sqs_record(
    message_id: str,
    body: object,
) -> dict[str, Any]:
    return {
        "messageId": (
            message_id
        ),
        "receiptHandle": (
            f"receipt-{message_id}"
        ),
        "body": (
            body
            if isinstance(
                body,
                str,
            )
            else json.dumps(
                body
            )
        ),
        "attributes": {
            "ApproximateReceiveCount": (
                "1"
            ),
        },
        "messageAttributes": {},
        "md5OfBody": (
            "test-md5"
        ),
        "eventSource": (
            "aws:sqs"
        ),
        "eventSourceARN": (
            "arn:aws:sqs:"
            "us-east-1:"
            "123456789012:"
            "opsflow-dev-task-queue"
        ),
        "awsRegion": (
            "us-east-1"
        ),
    }


def build_incident_processing_task(
) -> dict[str, Any]:
    task = (
        load_valid_task()
    )

    task[
        "task_id"
    ] = (
        "bb587a5f-3c94-4e03-"
        "8b13-159d8f58acfa"
    )

    task[
        "task_type"
    ] = (
        "incident.processing.requested"
    )

    task[
        "producer"
    ] = (
        "incident-service"
    )

    task[
        "correlation_id"
    ] = (
        "7385b223-c727-4297-"
        "ade2-d8089fa2d9c2"
    )

    task[
        "causation_id"
    ] = None

    task[
        "idempotency_key"
    ] = (
        "incident:"
        f"{INCIDENT_ID}:"
        "process:v1"
    )

    task[
        "payload"
    ] = {
        "incident_id": (
            INCIDENT_ID
        ),
    }

    task[
        "metadata"
    ] = {
        "source": (
            "incident-service"
        ),
        "operation": (
            "incident.create"
        ),
    }

    return task


def test_successful_batch_has_no_failures(
) -> None:
    valid_task = (
        load_valid_task()
    )

    event = {
        "Records": [
            create_sqs_record(
                "message-1",
                valid_task,
            ),
        ],
    }

    result = lambda_handler(
        event,
        None,
    )

    assert result == {
        "batchItemFailures": [],
    }


def test_incident_processing_task_is_accepted(
) -> None:
    processing_task = (
        build_incident_processing_task()
    )

    event = {
        "Records": [
            create_sqs_record(
                "incident-processing-message",
                processing_task,
            ),
        ],
    }

    result = lambda_handler(
        event,
        None,
    )

    assert result == {
        "batchItemFailures": [],
    }


def test_only_failed_record_is_reported(
) -> None:
    valid_task = (
        load_valid_task()
    )

    second_valid_task = (
        copy.deepcopy(
            valid_task
        )
    )

    second_valid_task[
        "task_id"
    ] = (
        "9e0cd004-6a31-4a92-"
        "aa88-d83777b1a2b0"
    )

    event = {
        "Records": [
            create_sqs_record(
                "message-good-1",
                valid_task,
            ),
            create_sqs_record(
                "message-bad",
                "{invalid-json",
            ),
            create_sqs_record(
                "message-good-2",
                second_valid_task,
            ),
        ],
    }

    result = lambda_handler(
        event,
        None,
    )

    assert result == {
        "batchItemFailures": [
            {
                "itemIdentifier": (
                    "message-bad"
                ),
            },
        ],
    }


def test_contract_failure_is_reported(
) -> None:
    invalid_task = (
        load_valid_task()
    )

    invalid_task.pop(
        "idempotency_key",
    )

    event = {
        "Records": [
            create_sqs_record(
                "message-invalid-contract",
                invalid_task,
            ),
        ],
    }

    result = lambda_handler(
        event,
        None,
    )

    assert result == {
        "batchItemFailures": [
            {
                "itemIdentifier": (
                    "message-invalid-contract"
                ),
            },
        ],
    }


def test_invalid_incident_processing_payload_is_reported(
) -> None:
    invalid_task = (
        build_incident_processing_task()
    )

    invalid_task[
        "payload"
    ] = {
        "incident_id": (
            "not-a-uuid"
        ),
    }

    event = {
        "Records": [
            create_sqs_record(
                "message-invalid-incident",
                invalid_task,
            ),
        ],
    }

    result = lambda_handler(
        event,
        None,
    )

    assert result == {
        "batchItemFailures": [
            {
                "itemIdentifier": (
                    "message-invalid-incident"
                ),
            },
        ],
    }
