from __future__ import annotations

from typing import (
    Any,
)

import pytest
from botocore.exceptions import (
    ClientError,
)

import task_worker.execution_state as execution_state_module
from task_worker.execution_state import (
    READY_FOR_INCIDENT_SERVICE_STATUS,
    TASK_EXECUTION_EXPIRATION_SECONDS_ENV,
    TASK_EXECUTION_TABLE_NAME_ENV,
    DynamoDbTaskExecutionStore,
    TaskExecutionCollisionError,
    TaskExecutionConfigurationError,
    TaskExecutionSettings,
    build_task_execution_store,
    load_task_execution_settings,
)

TASK_ID = (
    "bb587a5f-3c94-4e03-"
    "8b13-159d8f58acfa"
)

INCIDENT_ID = (
    "aca0a505-b460-4d08-"
    "9035-3b92bac0fff1"
)

CORRELATION_ID = (
    "7385b223-c727-4297-"
    "ade2-d8089fa2d9c2"
)

IDEMPOTENCY_KEY = (
    "incident:"
    f"{INCIDENT_ID}:"
    "process:v1"
)


def build_task(
) -> dict[str, Any]:
    return {
        "task_id": (
            TASK_ID
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
            CORRELATION_ID
        ),
        "causation_id": None,
        "idempotency_key": (
            IDEMPOTENCY_KEY
        ),
        "payload": {
            "incident_id": (
                INCIDENT_ID
            ),
        },
        "metadata": {
            "source": (
                "incident-service"
            ),
            "operation": (
                "incident.create"
            ),
        },
    }


class FakeDynamoDbTable:
    def __init__(
        self,
    ) -> None:
        self.items: dict[
            str,
            dict[str, Any],
        ] = {}

        self.fail_with_error_code: (
            str
            | None
        ) = None

    def put_item(
        self,
        *,
        Item: dict[str, Any],
        ConditionExpression: str,
    ) -> dict[str, Any]:
        assert (
            ConditionExpression
            == (
                "attribute_not_exists(task_id)"
            )
        )

        if (
            self.fail_with_error_code
            is not None
        ):
            raise (
                ClientError(
                    {
                        "Error": {
                            "Code": (
                                self.fail_with_error_code
                            ),
                            "Message": (
                                "simulated DynamoDB error"
                            ),
                        },
                    },
                    "PutItem",
                )
            )

        task_id = Item[
            "task_id"
        ]

        if task_id in self.items:
            raise (
                ClientError(
                    {
                        "Error": {
                            "Code": (
                                "ConditionalCheckFailedException"
                            ),
                            "Message": (
                                "task already exists"
                            ),
                        },
                    },
                    "PutItem",
                )
            )

        self.items[
            task_id
        ] = dict(
            Item
        )

        return {}

    def get_item(
        self,
        *,
        Key: dict[str, Any],
        ConsistentRead: bool,
    ) -> dict[str, Any]:
        assert (
            ConsistentRead
            is True
        )

        task_id = Key[
            "task_id"
        ]

        item = self.items.get(
            task_id
        )

        if item is None:
            return {}

        return {
            "Item": dict(
                item
            ),
        }


def test_load_settings_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        TASK_EXECUTION_TABLE_NAME_ENV,
        "execution-table",
    )

    monkeypatch.setenv(
        TASK_EXECUTION_EXPIRATION_SECONDS_ENV,
        "86400",
    )

    settings = (
        load_task_execution_settings()
    )

    assert settings == (
        TaskExecutionSettings(
            table_name=(
                "execution-table"
            ),
            expiration_seconds=(
                86400
            ),
        )
    )


def test_missing_table_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        TASK_EXECUTION_TABLE_NAME_ENV,
        raising=False,
    )

    monkeypatch.setenv(
        TASK_EXECUTION_EXPIRATION_SECONDS_ENV,
        "86400",
    )

    with pytest.raises(
        TaskExecutionConfigurationError,
        match=(
            "TASK_EXECUTION_TABLE_NAME "
            "must be configured"
        ),
    ):
        load_task_execution_settings()


def test_invalid_expiration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        TASK_EXECUTION_TABLE_NAME_ENV,
        "execution-table",
    )

    monkeypatch.setenv(
        TASK_EXECUTION_EXPIRATION_SECONDS_ENV,
        "not-a-number",
    )

    with pytest.raises(
        TaskExecutionConfigurationError,
        match=(
            "TASK_EXECUTION_EXPIRATION_SECONDS "
            "must be a whole number"
        ),
    ):
        load_task_execution_settings()


def test_build_store_uses_supplied_table(
) -> None:
    table = (
        FakeDynamoDbTable()
    )

    store = (
        build_task_execution_store(
            settings=(
                TaskExecutionSettings(
                    table_name=(
                        "execution-table"
                    ),
                    expiration_seconds=(
                        86400
                    ),
                )
            ),
            table=table,
        )
    )

    assert isinstance(
        store,
        DynamoDbTaskExecutionStore,
    )


def test_accept_creates_execution_record(
) -> None:
    table = (
        FakeDynamoDbTable()
    )

    store = (
        DynamoDbTaskExecutionStore(
            table_name=(
                "execution-table"
            ),
            expiration_seconds=(
                86400
            ),
            table=table,
        )
    )

    created = (
        store
        .accept_incident_processing_task(
            task=build_task(),
            incident_id=(
                INCIDENT_ID
            ),
        )
    )

    assert created is True

    persisted = (
        table.items[
            TASK_ID
        ]
    )

    assert (
        persisted[
            "task_id"
        ]
        == TASK_ID
    )

    assert (
        persisted[
            "incident_id"
        ]
        == INCIDENT_ID
    )

    assert (
        persisted[
            "task_type"
        ]
        == (
            "incident.processing.requested"
        )
    )

    assert (
        persisted[
            "idempotency_key"
        ]
        == IDEMPOTENCY_KEY
    )

    assert (
        persisted[
            "correlation_id"
        ]
        == CORRELATION_ID
    )

    assert (
        persisted[
            "status"
        ]
        == (
            READY_FOR_INCIDENT_SERVICE_STATUS
        )
    )

    assert (
        persisted[
            "reconciliation_attempts"
        ]
        == 0
    )

    assert (
        persisted[
            "payload"
        ]
        == {
            "incident_id": (
                INCIDENT_ID
            ),
        }
    )

    assert (
        persisted[
            "expiration"
        ]
        > 0
    )


def test_exact_retry_is_treated_as_existing(
) -> None:
    table = (
        FakeDynamoDbTable()
    )

    store = (
        DynamoDbTaskExecutionStore(
            table_name=(
                "execution-table"
            ),
            expiration_seconds=(
                86400
            ),
            table=table,
        )
    )

    task = build_task()

    first_created = (
        store
        .accept_incident_processing_task(
            task=task,
            incident_id=(
                INCIDENT_ID
            ),
        )
    )

    second_created = (
        store
        .accept_incident_processing_task(
            task=task,
            incident_id=(
                INCIDENT_ID
            ),
        )
    )

    assert first_created is True
    assert second_created is False

    assert len(
        table.items
    ) == 1


def test_conflicting_task_identity_is_rejected(
) -> None:
    table = (
        FakeDynamoDbTable()
    )

    store = (
        DynamoDbTaskExecutionStore(
            table_name=(
                "execution-table"
            ),
            expiration_seconds=(
                86400
            ),
            table=table,
        )
    )

    task = build_task()

    store.accept_incident_processing_task(
        task=task,
        incident_id=(
            INCIDENT_ID
        ),
    )

    conflicting_task = (
        build_task()
    )

    conflicting_task[
        "idempotency_key"
    ] = (
        "incident:"
        f"{INCIDENT_ID}:"
        "different-operation:v1"
    )

    with pytest.raises(
        TaskExecutionCollisionError,
        match=(
            "idempotency_key"
        ),
    ):
        (
            store
            .accept_incident_processing_task(
                task=(
                    conflicting_task
                ),
                incident_id=(
                    INCIDENT_ID
                ),
            )
        )


def test_nonconditional_dynamodb_error_propagates(
) -> None:
    table = (
        FakeDynamoDbTable()
    )

    table.fail_with_error_code = (
        "ProvisionedThroughputExceededException"
    )

    store = (
        DynamoDbTaskExecutionStore(
            table_name=(
                "execution-table"
            ),
            expiration_seconds=(
                86400
            ),
            table=table,
        )
    )

    with pytest.raises(
        ClientError,
    ):
        (
            store
            .accept_incident_processing_task(
                task=build_task(),
                incident_id=(
                    INCIDENT_ID
                ),
            )
        )


def test_get_store_initializes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_store = object()

    build_count = 0

    def fake_build(
    ) -> object:
        nonlocal build_count

        build_count += 1

        return expected_store

    monkeypatch.setattr(
        execution_state_module,
        "_execution_store",
        None,
    )

    monkeypatch.setattr(
        execution_state_module,
        "build_task_execution_store",
        fake_build,
    )

    first = (
        execution_state_module
        .get_task_execution_store()
    )

    second = (
        execution_state_module
        .get_task_execution_store()
    )

    assert first is expected_store
    assert second is expected_store
    assert build_count == 1
