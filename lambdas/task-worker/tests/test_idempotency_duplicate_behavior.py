from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from aws_lambda_powertools.utilities.idempotency import (
    BasePersistenceLayer,
    IdempotencyConfig,
)
from aws_lambda_powertools.utilities.idempotency.exceptions import (
    IdempotencyItemAlreadyExistsError,
    IdempotencyItemNotFoundError,
)
from aws_lambda_powertools.utilities.idempotency.persistence.datarecord import (
    DataRecord,
)

import task_worker.handler as handler_module
import task_worker.idempotency as idempotency_module
from task_worker.idempotency import (
    IDEMPOTENCY_KEY_PREFIX,
    IdempotencyRuntime,
    build_idempotent_task_processor,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

VALID_FIXTURE_PATH = (
    REPOSITORY_ROOT
    / "contracts"
    / "tasks"
    / "fixtures"
    / "valid-task-v1.json"
)


class InMemoryPersistenceLayer(
    BasePersistenceLayer,
):
    """Minimal Powertools persistence layer for behavior tests."""

    def __init__(self) -> None:
        self.records: dict[str, DataRecord] = {}

        self.deleted_keys: list[str] = []

        super().__init__()

    def _get_record(
        self,
        idempotency_key: str,
    ) -> DataRecord:
        try:
            return self.records[
                idempotency_key
            ]
        except KeyError as exc:
            raise IdempotencyItemNotFoundError(
                idempotency_key
            ) from exc

    def _put_record(
        self,
        data_record: DataRecord,
    ) -> None:
        existing_record = self.records.get(
            data_record.idempotency_key
        )

        if (
            existing_record is not None
            and not existing_record.is_expired
        ):
            raise IdempotencyItemAlreadyExistsError(
                data_record.idempotency_key,
                old_data_record=existing_record,
            )

        self.records[
            data_record.idempotency_key
        ] = data_record

    def _update_record(
        self,
        data_record: DataRecord,
    ) -> None:
        self.records[
            data_record.idempotency_key
        ] = data_record

    def _delete_record(
        self,
        data_record: DataRecord,
    ) -> None:
        self.deleted_keys.append(
            data_record.idempotency_key
        )

        self.records.pop(
            data_record.idempotency_key,
            None,
        )


class FakeLambdaContext:
    """Lambda context exposing remaining execution time."""

    def get_remaining_time_in_millis(
        self,
    ) -> int:
        return 30000


def load_valid_task() -> dict[str, Any]:
    with VALID_FIXTURE_PATH.open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        return json.load(fixture_file)


def create_sqs_record(
    message_id: str,
    task: dict[str, Any],
) -> dict[str, Any]:
    return {
        "messageId": message_id,
        "body": json.dumps(task),
    }


def create_test_runtime(
) -> tuple[
    IdempotencyRuntime,
    InMemoryPersistenceLayer,
]:
    persistence_store = (
        InMemoryPersistenceLayer()
    )

    config = IdempotencyConfig(
        event_key_jmespath="idempotency_key",
        raise_on_no_idempotency_key=True,
        expires_after_seconds=2592000,
        use_local_cache=False,
    )

    runtime = IdempotencyRuntime(
        config=config,
        persistence_store=persistence_store,
    )

    return (
        runtime,
        persistence_store,
    )


def install_test_runtime(
    monkeypatch: pytest.MonkeyPatch,
    runtime: IdempotencyRuntime,
) -> None:
    idempotent_processor = (
        build_idempotent_task_processor(
            runtime=runtime,
        )
    )

    monkeypatch.setattr(
        idempotency_module,
        "_runtime",
        runtime,
    )

    monkeypatch.setattr(
        idempotency_module,
        "_idempotent_task_processor",
        idempotent_processor,
    )


def test_duplicate_logical_tasks_execute_processor_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, persistence_store = (
        create_test_runtime()
    )

    install_test_runtime(
        monkeypatch,
        runtime,
    )

    first_task = load_valid_task()

    duplicate_task = copy.deepcopy(
        first_task
    )

    duplicate_task["task_id"] = (
        "925c5c3c-54df-4f52-"
        "a287-2c6e32907662"
    )

    assert (
        duplicate_task["idempotency_key"]
        == first_task["idempotency_key"]
    )

    processed_task_ids: list[str] = []

    def record_processing(
        task: dict[str, Any],
    ) -> None:
        processed_task_ids.append(
            task["task_id"]
        )

    monkeypatch.setattr(
        handler_module,
        "dispatch_task",
        record_processing,
    )

    event = {
        "Records": [
            create_sqs_record(
                "message-original",
                first_task,
            ),
            create_sqs_record(
                "message-duplicate",
                duplicate_task,
            ),
        ],
    }

    result = handler_module.lambda_handler(
        event,
        FakeLambdaContext(),
    )

    assert result == {
        "batchItemFailures": [],
    }

    assert processed_task_ids == [
        first_task["task_id"],
    ]

    assert len(
        persistence_store.records
    ) == 1

    persisted_record = next(
        iter(
            persistence_store.records.values()
        )
    )

    assert persisted_record.status == "COMPLETED"

    assert persisted_record.idempotency_key.startswith(
        f"{IDEMPOTENCY_KEY_PREFIX}#"
    )


def test_different_idempotency_keys_execute_independently() -> None:
    runtime, persistence_store = (
        create_test_runtime()
    )

    processor = (
        build_idempotent_task_processor(
            runtime=runtime,
        )
    )

    processed_keys: list[str] = []

    def record_processing(
        task: dict[str, Any],
    ) -> None:
        processed_keys.append(
            task["idempotency_key"]
        )

    first_task = {
        "idempotency_key": (
            "logical-operation-a"
        ),
    }

    second_task = {
        "idempotency_key": (
            "logical-operation-b"
        ),
    }

    processor(
        task=first_task,
        processor=record_processing,
    )

    processor(
        task=second_task,
        processor=record_processing,
    )

    assert processed_keys == [
        "logical-operation-a",
        "logical-operation-b",
    ]

    assert len(
        persistence_store.records
    ) == 2


def test_failed_operation_deletes_record_and_can_retry() -> None:
    runtime, persistence_store = (
        create_test_runtime()
    )

    processor = (
        build_idempotent_task_processor(
            runtime=runtime,
        )
    )

    task = {
        "idempotency_key": (
            "logical-operation-retry"
        ),
    }

    attempt_count = 0

    def flaky_processing(
        task: dict[str, Any],
    ) -> None:
        nonlocal attempt_count

        attempt_count += 1

        if attempt_count == 1:
            raise RuntimeError(
                "simulated processing failure"
            )

    with pytest.raises(
        RuntimeError,
        match="simulated processing failure",
    ):
        processor(
            task=task,
            processor=flaky_processing,
        )

    assert attempt_count == 1

    assert persistence_store.records == {}

    assert len(
        persistence_store.deleted_keys
    ) == 1

    processor(
        task=task,
        processor=flaky_processing,
    )

    assert attempt_count == 2

    assert len(
        persistence_store.records
    ) == 1

    persisted_record = next(
        iter(
            persistence_store.records.values()
        )
    )

    assert persisted_record.status == "COMPLETED"


def test_failed_sqs_record_succeeds_on_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, persistence_store = (
        create_test_runtime()
    )

    install_test_runtime(
        monkeypatch,
        runtime,
    )

    task = load_valid_task()

    attempts: list[str] = []

    def flaky_dispatch(
        task: dict[str, Any],
    ) -> None:
        attempts.append(
            task["task_id"]
        )

        if len(attempts) == 1:
            raise RuntimeError(
                "simulated downstream failure"
            )

    monkeypatch.setattr(
        handler_module,
        "dispatch_task",
        flaky_dispatch,
    )

    first_event = {
        "Records": [
            create_sqs_record(
                "message-retryable",
                task,
            ),
        ],
    }

    first_result = (
        handler_module.lambda_handler(
            first_event,
            FakeLambdaContext(),
        )
    )

    assert first_result == {
        "batchItemFailures": [
            {
                "itemIdentifier": (
                    "message-retryable"
                ),
            },
        ],
    }

    assert attempts == [
        task["task_id"],
    ]

    assert persistence_store.records == {}

    assert len(
        persistence_store.deleted_keys
    ) == 1

    retry_event = {
        "Records": [
            create_sqs_record(
                "message-retryable",
                task,
            ),
        ],
    }

    retry_result = (
        handler_module.lambda_handler(
            retry_event,
            FakeLambdaContext(),
        )
    )

    assert retry_result == {
        "batchItemFailures": [],
    }

    assert attempts == [
        task["task_id"],
        task["task_id"],
    ]

    assert len(
        persistence_store.records
    ) == 1

    persisted_record = next(
        iter(
            persistence_store.records.values()
        )
    )

    assert persisted_record.status == "COMPLETED"
