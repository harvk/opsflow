"""Durable DynamoDB execution state for OpsFlow asynchronous tasks."""

from __future__ import annotations

import os
from dataclasses import (
    dataclass,
)
from datetime import (
    UTC,
    datetime,
)
from time import (
    time,
)
from typing import (
    Any,
)

import boto3
from botocore.exceptions import (
    ClientError,
)

TASK_EXECUTION_TABLE_NAME_ENV = (
    "TASK_EXECUTION_TABLE_NAME"
)

TASK_EXECUTION_EXPIRATION_SECONDS_ENV = (
    "TASK_EXECUTION_EXPIRATION_SECONDS"
)

READY_FOR_INCIDENT_SERVICE_STATUS = (
    "READY_FOR_INCIDENT_SERVICE"
)

MINIMUM_EXECUTION_EXPIRATION_SECONDS = (
    60
)


class TaskExecutionConfigurationError(
    RuntimeError
):
    """
    Raised when task execution-state configuration is invalid.
    """


class TaskExecutionCollisionError(
    RuntimeError
):
    """
    Raised when an existing task_id refers to different
    execution data.
    """


@dataclass(
    frozen=True,
)
class TaskExecutionSettings:
    """
    Validated runtime configuration for task execution state.
    """

    table_name: str

    expiration_seconds: int


class DynamoDbTaskExecutionStore:
    """
    DynamoDB-backed execution-state store.

    The first successful writer creates the execution record.

    A retry of the same canonical task is treated as
    successful when the existing task_id carries the same
    Incident, task type, and idempotency key.

    A conflicting record using the same task_id is rejected.
    """

    def __init__(
        self,
        *,
        table_name: str,
        expiration_seconds: int,
        table: Any | None = None,
    ) -> None:
        self._expiration_seconds = (
            expiration_seconds
        )

        if table is not None:
            self._table = table

        else:
            dynamodb: Any = (
                boto3.resource(
                    "dynamodb"
                )
            )

            self._table = (
                dynamodb.Table(
                    table_name
                )
            )

    def accept_incident_processing_task(
        self,
        *,
        task: dict[str, Any],
        incident_id: str,
    ) -> bool:
        """
        Persist a durable Incident task execution record.

        Returns True when a new record is created.

        Returns False when the exact same task execution
        already exists.

        Raises TaskExecutionCollisionError when task_id is
        already associated with different execution data.
        """

        accepted_at = (
            datetime.now(
                UTC
            )
            .isoformat()
        )

        expiration = (
            int(
                time()
            )
            + self._expiration_seconds
        )

        item: dict[
            str,
            Any,
        ] = {
            "task_id": (
                task[
                    "task_id"
                ]
            ),
            "incident_id": (
                incident_id
            ),
            "task_type": (
                task[
                    "task_type"
                ]
            ),
            "schema_version": (
                task[
                    "schema_version"
                ]
            ),
            "producer": (
                task[
                    "producer"
                ]
            ),
            "idempotency_key": (
                task[
                    "idempotency_key"
                ]
            ),
            "correlation_id": (
                task[
                    "correlation_id"
                ]
            ),
            "status": (
                READY_FOR_INCIDENT_SERVICE_STATUS
            ),
            "payload": (
                task[
                    "payload"
                ]
            ),
            "created_at": (
                task[
                    "created_at"
                ]
            ),
            "accepted_at": (
                accepted_at
            ),
            "updated_at": (
                accepted_at
            ),
            "reconciliation_attempts": (
                0
            ),
            "expiration": (
                expiration
            ),
        }

        causation_id = (
            task.get(
                "causation_id"
            )
        )

        if causation_id is not None:
            item[
                "causation_id"
            ] = causation_id

        metadata = (
            task.get(
                "metadata"
            )
        )

        if metadata is not None:
            item[
                "metadata"
            ] = metadata

        try:
            self._table.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists(task_id)"
                ),
            )

        except ClientError as exc:
            error_code = (
                exc.response
                .get(
                    "Error",
                    {},
                )
                .get(
                    "Code"
                )
            )

            if (
                error_code
                != (
                    "ConditionalCheckFailedException"
                )
            ):
                raise

            existing_response = (
                self._table.get_item(
                    Key={
                        "task_id": (
                            task[
                                "task_id"
                            ]
                        ),
                    },
                    ConsistentRead=True,
                )
            )

            existing_item = (
                existing_response.get(
                    "Item"
                )
            )

            if not isinstance(
                existing_item,
                dict,
            ):
                raise (
                    TaskExecutionCollisionError(
                        "Task execution record reported "
                        "an existing task_id but could "
                        "not be loaded"
                    )
                ) from exc

            self._validate_existing_record(
                existing_item=(
                    existing_item
                ),
                task=task,
                incident_id=(
                    incident_id
                ),
            )

            return False

        return True

    @staticmethod
    def _validate_existing_record(
        *,
        existing_item: dict[str, Any],
        task: dict[str, Any],
        incident_id: str,
    ) -> None:
        expected_values = {
            "task_id": (
                task[
                    "task_id"
                ]
            ),
            "incident_id": (
                incident_id
            ),
            "task_type": (
                task[
                    "task_type"
                ]
            ),
            "idempotency_key": (
                task[
                    "idempotency_key"
                ]
            ),
            "correlation_id": (
                task[
                    "correlation_id"
                ]
            ),
        }

        mismatched_fields = [
            field_name
            for (
                field_name,
                expected_value,
            )
            in expected_values.items()
            if (
                existing_item.get(
                    field_name
                )
                != expected_value
            )
        ]

        if mismatched_fields:
            fields = ", ".join(
                sorted(
                    mismatched_fields
                )
            )

            raise (
                TaskExecutionCollisionError(
                    "Existing task execution record "
                    "conflicts with the incoming task for "
                    f"fields: {fields}"
                )
            )


_execution_store: (
    DynamoDbTaskExecutionStore
    | None
) = None


def _required_environment_variable(
    name: str,
) -> str:
    value = os.getenv(
        name
    )

    if (
        value is None
        or not value.strip()
    ):
        raise (
            TaskExecutionConfigurationError(
                f"{name} must be configured"
            )
        )

    return value.strip()


def load_task_execution_settings(
) -> TaskExecutionSettings:
    """
    Load and validate task execution-state settings.
    """

    table_name = (
        _required_environment_variable(
            TASK_EXECUTION_TABLE_NAME_ENV
        )
    )

    raw_expiration_seconds = (
        _required_environment_variable(
            TASK_EXECUTION_EXPIRATION_SECONDS_ENV
        )
    )

    try:
        expiration_seconds = int(
            raw_expiration_seconds
        )

    except ValueError as exc:
        raise (
            TaskExecutionConfigurationError(
                f"{TASK_EXECUTION_EXPIRATION_SECONDS_ENV} "
                "must be a whole number"
            )
        ) from exc

    if (
        expiration_seconds
        < MINIMUM_EXECUTION_EXPIRATION_SECONDS
    ):
        raise (
            TaskExecutionConfigurationError(
                f"{TASK_EXECUTION_EXPIRATION_SECONDS_ENV} "
                "must be at least "
                f"{MINIMUM_EXECUTION_EXPIRATION_SECONDS}"
            )
        )

    return (
        TaskExecutionSettings(
            table_name=table_name,
            expiration_seconds=(
                expiration_seconds
            ),
        )
    )


def build_task_execution_store(
    settings: (
        TaskExecutionSettings
        | None
    ) = None,
    *,
    table: Any | None = None,
) -> DynamoDbTaskExecutionStore:
    """
    Build the task execution-state persistence adapter.
    """

    resolved_settings = (
        settings
        if settings is not None
        else (
            load_task_execution_settings()
        )
    )

    return (
        DynamoDbTaskExecutionStore(
            table_name=(
                resolved_settings
                .table_name
            ),
            expiration_seconds=(
                resolved_settings
                .expiration_seconds
            ),
            table=table,
        )
    )


def get_task_execution_store(
) -> DynamoDbTaskExecutionStore:
    """
    Return the lazily initialized execution-state store.
    """

    global _execution_store

    if _execution_store is None:
        _execution_store = (
            build_task_execution_store()
        )

    return _execution_store
