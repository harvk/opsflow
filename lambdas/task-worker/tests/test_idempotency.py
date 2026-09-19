from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from aws_lambda_powertools.utilities.idempotency import (
    BasePersistenceLayer,
    IdempotencyConfig,
)
from aws_lambda_powertools.utilities.idempotency.exceptions import (
    IdempotencyKeyError,
)
from aws_lambda_powertools.utilities.idempotency.persistence.datarecord import (
    DataRecord,
)

import task_worker.idempotency as idempotency_module
from task_worker.idempotency import (
    IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
    IDEMPOTENCY_KEY_PREFIX,
    IDEMPOTENCY_TABLE_NAME_ENV,
    MINIMUM_EXPIRATION_SECONDS,
    IdempotencyConfigurationError,
    IdempotencyRuntime,
    IdempotencySettings,
    build_idempotency_runtime,
    build_idempotent_task_processor,
    get_idempotency_runtime,
    get_idempotent_task_processor,
    load_idempotency_settings,
    process_task_idempotently,
    register_lambda_context,
)


class UnexpectedPersistenceLayer(
    BasePersistenceLayer,
):
    """Persistence layer that fails if storage access is attempted."""

    def _get_record(
        self,
        idempotency_key: str,
    ) -> DataRecord:
        raise AssertionError(
            "Persistence read was not expected"
        )

    def _put_record(
        self,
        data_record: DataRecord,
    ) -> None:
        raise AssertionError(
            "Persistence write was not expected"
        )

    def _update_record(
        self,
        data_record: DataRecord,
    ) -> None:
        raise AssertionError(
            "Persistence update was not expected"
        )

    def _delete_record(
        self,
        data_record: DataRecord,
    ) -> None:
        raise AssertionError(
            "Persistence delete was not expected"
        )


def test_load_idempotency_settings_parses_valid_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        "  opsflow-dev-task-worker-idempotency  ",
    )

    monkeypatch.setenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        " 2592000 ",
    )

    settings = load_idempotency_settings()

    assert settings == IdempotencySettings(
        table_name=(
            "opsflow-dev-task-worker-idempotency"
        ),
        expiration_seconds=2592000,
    )


def test_missing_table_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        raising=False,
    )

    monkeypatch.setenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        "2592000",
    )

    with pytest.raises(
        IdempotencyConfigurationError,
        match=(
            "IDEMPOTENCY_TABLE_NAME "
            "must be configured"
        ),
    ):
        load_idempotency_settings()


def test_blank_table_name_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        "   ",
    )

    monkeypatch.setenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        "2592000",
    )

    with pytest.raises(
        IdempotencyConfigurationError,
        match=(
            "IDEMPOTENCY_TABLE_NAME "
            "must be configured"
        ),
    ):
        load_idempotency_settings()


def test_missing_expiration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        "opsflow-dev-task-worker-idempotency",
    )

    monkeypatch.delenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        raising=False,
    )

    with pytest.raises(
        IdempotencyConfigurationError,
        match=(
            "IDEMPOTENCY_EXPIRATION_SECONDS "
            "must be configured"
        ),
    ):
        load_idempotency_settings()


def test_nonnumeric_expiration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        "opsflow-dev-task-worker-idempotency",
    )

    monkeypatch.setenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        "thirty-days",
    )

    with pytest.raises(
        IdempotencyConfigurationError,
        match=(
            "IDEMPOTENCY_EXPIRATION_SECONDS "
            "must be a whole number"
        ),
    ):
        load_idempotency_settings()


def test_expiration_below_minimum_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        IDEMPOTENCY_TABLE_NAME_ENV,
        "opsflow-dev-task-worker-idempotency",
    )

    monkeypatch.setenv(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
        str(
            MINIMUM_EXPIRATION_SECONDS - 1
        ),
    )

    with pytest.raises(
        IdempotencyConfigurationError,
        match=(
            "IDEMPOTENCY_EXPIRATION_SECONDS "
            "must be at least 60"
        ),
    ):
        load_idempotency_settings()


def test_build_runtime_configures_powertools_correctly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_table_names: list[str] = []

    persistence_store = object()

    def fake_persistence_layer(
        *,
        table_name: str,
    ) -> object:
        captured_table_names.append(
            table_name
        )

        return persistence_store

    monkeypatch.setattr(
        idempotency_module,
        "DynamoDBPersistenceLayer",
        fake_persistence_layer,
    )

    runtime = build_idempotency_runtime(
        settings=IdempotencySettings(
            table_name="unit-test-table",
            expiration_seconds=86400,
        ),
    )

    assert captured_table_names == [
        "unit-test-table",
    ]

    assert (
        runtime.persistence_store
        is persistence_store
    )

    assert (
        runtime.config.event_key_jmespath
        == "idempotency_key"
    )

    assert (
        runtime.config.raise_on_no_idempotency_key
        is True
    )

    assert (
        runtime.config.expires_after_seconds
        == 86400
    )

    assert runtime.config.use_local_cache is False


def test_get_runtime_builds_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_store = (
        UnexpectedPersistenceLayer()
    )

    expected_runtime = IdempotencyRuntime(
        config=IdempotencyConfig(),
        persistence_store=persistence_store,
    )

    build_count = 0

    def fake_build_runtime() -> IdempotencyRuntime:
        nonlocal build_count

        build_count += 1

        return expected_runtime

    monkeypatch.setattr(
        idempotency_module,
        "_runtime",
        None,
    )

    monkeypatch.setattr(
        idempotency_module,
        "build_idempotency_runtime",
        fake_build_runtime,
    )

    first_runtime = get_idempotency_runtime()

    second_runtime = get_idempotency_runtime()

    assert first_runtime is expected_runtime

    assert second_runtime is expected_runtime

    assert build_count == 1


def test_build_task_processor_configures_decorator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_store = (
        UnexpectedPersistenceLayer()
    )

    config = IdempotencyConfig()

    runtime = IdempotencyRuntime(
        config=config,
        persistence_store=persistence_store,
    )

    captured: dict[str, Any] = {}

    def sentinel_processor(
        **_kwargs: Any,
    ) -> None:
        return None

    def fake_idempotent_function(
        **kwargs: Any,
    ) -> Callable[
        [Callable[..., Any]],
        Callable[..., Any],
    ]:
        captured.update(
            kwargs
        )

        def decorator(
            function: Callable[..., Any],
        ) -> Callable[..., Any]:
            captured["function"] = function

            return sentinel_processor

        return decorator

    monkeypatch.setattr(
        idempotency_module,
        "idempotent_function",
        fake_idempotent_function,
    )

    built_processor = (
        build_idempotent_task_processor(
            runtime=runtime,
        )
    )

    assert (
        built_processor
        is sentinel_processor
    )

    assert (
        captured["data_keyword_argument"]
        == "task"
    )

    assert (
        captured["persistence_store"]
        is persistence_store
    )

    assert captured["config"] is config

    assert (
        captured["key_prefix"]
        == IDEMPOTENCY_KEY_PREFIX
    )

    assert (
        captured["function"]
        is idempotency_module._invoke_task_processor
    )


def test_get_task_processor_builds_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_count = 0

    def expected_processor(
        **_kwargs: Any,
    ) -> None:
        return None

    def fake_build_processor(
    ) -> Callable[..., None]:
        nonlocal build_count

        build_count += 1

        return expected_processor

    monkeypatch.setattr(
        idempotency_module,
        "_idempotent_task_processor",
        None,
    )

    monkeypatch.setattr(
        idempotency_module,
        "build_idempotent_task_processor",
        fake_build_processor,
    )

    first_processor = (
        get_idempotent_task_processor()
    )

    second_processor = (
        get_idempotent_task_processor()
    )

    assert (
        first_processor
        is expected_processor
    )

    assert (
        second_processor
        is expected_processor
    )

    assert build_count == 1


def test_process_task_idempotently_delegates_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    task = {
        "idempotency_key": (
            "unit-test-operation"
        ),
    }

    def business_processor(
        task: dict[str, Any],
    ) -> None:
        return None

    def fake_idempotent_processor(
        **kwargs: Any,
    ) -> None:
        captured.update(
            kwargs
        )

    monkeypatch.setattr(
        idempotency_module,
        "get_idempotent_task_processor",
        lambda: fake_idempotent_processor,
    )

    process_task_idempotently(
        task=task,
        processor=business_processor,
    )

    assert captured["task"] is task

    assert (
        captured["processor"]
        is business_processor
    )


def test_register_lambda_context_delegates_to_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_store = (
        UnexpectedPersistenceLayer()
    )

    config = IdempotencyConfig()

    runtime = IdempotencyRuntime(
        config=config,
        persistence_store=persistence_store,
    )

    monkeypatch.setattr(
        idempotency_module,
        "get_idempotency_runtime",
        lambda: runtime,
    )

    context = object()

    register_lambda_context(
        context,
    )

    assert config.lambda_context is context


def test_missing_idempotency_key_is_rejected_before_processing() -> None:
    persistence_store = (
        UnexpectedPersistenceLayer()
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

    processor = (
        build_idempotent_task_processor(
            runtime=runtime,
        )
    )

    business_processor_called = False

    def business_processor(
        task: dict[str, Any],
    ) -> None:
        nonlocal business_processor_called

        business_processor_called = True

    with pytest.raises(
        IdempotencyKeyError,
    ):
        processor(
            task={
                "task_id": (
                    "missing-idempotency-key"
                ),
            },
            processor=business_processor,
        )

    assert business_processor_called is False
