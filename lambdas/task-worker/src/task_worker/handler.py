"""AWS Lambda entry point for OpsFlow SQS task processing."""

from __future__ import annotations

import json
from typing import Any

from task_worker.contracts import validate_task_envelope
from task_worker.dispatcher import dispatch_task


class InvalidSqsRecordError(ValueError):
    """Raised when an incoming SQS record is malformed."""


def _structured_log(
    level: str,
    event: str,
    **fields: Any,
) -> None:
    print(
        json.dumps(
            {
                "level": level,
                "event": event,
                **fields,
            },
            sort_keys=True,
            default=str,
        )
    )


def _parse_record_body(
    record: dict[str, Any],
) -> Any:
    body = record.get("body")

    if not isinstance(body, str):
        raise InvalidSqsRecordError(
            "SQS record body must be a string"
        )

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise InvalidSqsRecordError(
            "SQS record body must contain valid JSON"
        ) from exc


def process_record(
    record: dict[str, Any],
) -> None:
    """Process one SQS record."""

    task_candidate = _parse_record_body(record)

    task = validate_task_envelope(
        task_candidate,
    )

    _structured_log(
        "info",
        "task_processing_started",
        sqs_message_id=record.get("messageId"),
        task_id=task["task_id"],
        task_type=task["task_type"],
        correlation_id=task["correlation_id"],
        idempotency_key=task["idempotency_key"],
    )

    dispatch_task(task)

    _structured_log(
        "info",
        "task_processing_completed",
        sqs_message_id=record.get("messageId"),
        task_id=task["task_id"],
        task_type=task["task_type"],
        correlation_id=task["correlation_id"],
        idempotency_key=task["idempotency_key"],
    )


def lambda_handler(
    event: dict[str, Any],
    _context: Any,
) -> dict[str, list[dict[str, str]]]:
    """Process an SQS batch and report individual failures."""

    records = event.get("Records")

    if not isinstance(records, list):
        raise InvalidSqsRecordError(
            "Lambda event must contain a Records list"
        )

    batch_item_failures: list[dict[str, str]] = []

    for record_candidate in records:
        if not isinstance(record_candidate, dict):
            raise InvalidSqsRecordError(
                "Each SQS record must be an object"
            )

        message_id = record_candidate.get(
            "messageId",
        )

        if not isinstance(message_id, str) or not message_id:
            raise InvalidSqsRecordError(
                "Each SQS record must contain messageId"
            )

        try:
            process_record(record_candidate)
        except Exception as exc:
            _structured_log(
                "error",
                "task_processing_failed",
                sqs_message_id=message_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )

            batch_item_failures.append(
                {
                    "itemIdentifier": message_id,
                }
            )

    return {
        "batchItemFailures": batch_item_failures,
    }