"""Idempotency configuration for OpsFlow task processing."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aws_lambda_powertools.utilities.idempotency import (
    BasePersistenceLayer,
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent_function,
)


IDEMPOTENCY_TABLE_NAME_ENV = "IDEMPOTENCY_TABLE_NAME"

IDEMPOTENCY_EXPIRATION_SECONDS_ENV = (
    "IDEMPOTENCY_EXPIRATION_SECONDS"
)

IDEMPOTENCY_KEY_PREFIX = "opsflow-task-worker"

MINIMUM_EXPIRATION_SECONDS = 60

TaskProcessor = Callable[[dict[str, Any]], None]

IdempotentTaskProcessor = Callable[..., None]


class IdempotencyConfigurationError(RuntimeError):
    """Raised when task-worker idempotency configuration is invalid."""


@dataclass(frozen=True)
class IdempotencySettings:
    """Validated runtime settings for task-worker idempotency."""

    table_name: str
    expiration_seconds: int


@dataclass(frozen=True)
class IdempotencyRuntime:
    """Powertools objects used by the task-worker idempotency boundary."""

    config: IdempotencyConfig
    persistence_store: BasePersistenceLayer


_runtime: IdempotencyRuntime | None = None

_idempotent_task_processor: IdempotentTaskProcessor | None = None


def _required_environment_variable(
    name: str,
) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise IdempotencyConfigurationError(
            f"{name} must be configured"
        )

    return value.strip()


def load_idempotency_settings() -> IdempotencySettings:
    """Load and validate idempotency settings from the environment."""

    table_name = _required_environment_variable(
        IDEMPOTENCY_TABLE_NAME_ENV,
    )

    raw_expiration_seconds = _required_environment_variable(
        IDEMPOTENCY_EXPIRATION_SECONDS_ENV,
    )

    try:
        expiration_seconds = int(
            raw_expiration_seconds,
        )
    except ValueError as exc:
        raise IdempotencyConfigurationError(
            f"{IDEMPOTENCY_EXPIRATION_SECONDS_ENV} "
            "must be a whole number"
        ) from exc

    if expiration_seconds < MINIMUM_EXPIRATION_SECONDS:
        raise IdempotencyConfigurationError(
            f"{IDEMPOTENCY_EXPIRATION_SECONDS_ENV} "
            f"must be at least {MINIMUM_EXPIRATION_SECONDS}"
        )

    return IdempotencySettings(
        table_name=table_name,
        expiration_seconds=expiration_seconds,
    )


def build_idempotency_runtime(
    settings: IdempotencySettings | None = None,
) -> IdempotencyRuntime:
    """Build the Powertools configuration and DynamoDB persistence layer."""

    resolved_settings = (
        settings
        if settings is not None
        else load_idempotency_settings()
    )

    config = IdempotencyConfig(
        event_key_jmespath="idempotency_key",
        raise_on_no_idempotency_key=True,
        expires_after_seconds=(
            resolved_settings.expiration_seconds
        ),
        use_local_cache=False,
    )

    persistence_store = DynamoDBPersistenceLayer(
        table_name=resolved_settings.table_name,
    )

    return IdempotencyRuntime(
        config=config,
        persistence_store=persistence_store,
    )


def get_idempotency_runtime() -> IdempotencyRuntime:
    """Return the lazily initialized idempotency runtime."""

    global _runtime

    if _runtime is None:
        _runtime = build_idempotency_runtime()

    return _runtime


def _invoke_task_processor(
    *,
    task: dict[str, Any],
    processor: TaskProcessor,
) -> None:
    processor(task)


def build_idempotent_task_processor(
    runtime: IdempotencyRuntime | None = None,
) -> IdempotentTaskProcessor:
    """Build the idempotent wrapper around one task-processing operation."""

    resolved_runtime = (
        runtime
        if runtime is not None
        else get_idempotency_runtime()
    )

    return idempotent_function(
        data_keyword_argument="task",
        persistence_store=(
            resolved_runtime.persistence_store
        ),
        config=resolved_runtime.config,
        key_prefix=IDEMPOTENCY_KEY_PREFIX,
    )(_invoke_task_processor)


def get_idempotent_task_processor() -> IdempotentTaskProcessor:
    """Return the lazily initialized idempotent task processor."""

    global _idempotent_task_processor

    if _idempotent_task_processor is None:
        _idempotent_task_processor = (
            build_idempotent_task_processor()
        )

    return _idempotent_task_processor


def process_task_idempotently(
    *,
    task: dict[str, Any],
    processor: TaskProcessor,
) -> None:
    """Execute one validated task through the idempotency boundary."""

    idempotent_processor = (
        get_idempotent_task_processor()
    )

    idempotent_processor(
        task=task,
        processor=processor,
    )


def register_lambda_context(
    context: Any,
) -> None:
    """Register Lambda invocation context for in-progress expiration."""

    runtime = get_idempotency_runtime()

    runtime.config.register_lambda_context(
        context,
    )
