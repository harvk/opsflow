from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import task_worker.handler as handler_module
from task_worker.handler import (
    lambda_handler,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

VALID_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "tasks"
    / "fixtures"
    / "valid-task-v1.json"
)

TaskProcessor = Callable[[dict[str, Any]], None]


@pytest.fixture(autouse=True)
def bypass_idempotency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep handler unit tests independent from DynamoDB."""

    def register_context_directly(
        _context: Any,
    ) -> None:
        return None

    def process_directly(
        *,
        task: dict[str, Any],
        processor: TaskProcessor,
    ) -> None:
        processor(task)

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


def load_valid_task() -> dict[str, Any]:
    with VALID_FIXTURE_PATH.open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        return json.load(fixture_file)


def create_sqs_record(
    message_id: str,
    body: object,
) -> dict[str, Any]:
    return {
        "messageId": message_id,
        "receiptHandle": (
            f"receipt-{message_id}"
        ),
        "body": (
            body
            if isinstance(body, str)
            else json.dumps(body)
        ),
        "attributes": {
            "ApproximateReceiveCount": "1",
        },
        "messageAttributes": {},
        "md5OfBody": "test-md5",
        "eventSource": "aws:sqs",
        "eventSourceARN": (
            "arn:aws:sqs:"
            "us-east-1:"
            "123456789012:"
            "opsflow-dev-task-queue"
        ),
        "awsRegion": "us-east-1",
    }


def test_successful_batch_has_no_failures() -> None:
    valid_task = load_valid_task()

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


def test_only_failed_record_is_reported() -> None:
    valid_task = load_valid_task()

    second_valid_task = copy.deepcopy(
        valid_task,
    )

    second_valid_task["task_id"] = (
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


def test_contract_failure_is_reported() -> None:
    invalid_task = load_valid_task()

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
