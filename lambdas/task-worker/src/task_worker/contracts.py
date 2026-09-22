"""Validation of OpsFlow task envelopes against the canonical v1 contract."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


class TaskContractConfigurationError(RuntimeError):
    """Raised when the canonical task schema cannot be located."""


class InvalidTaskEnvelopeError(ValueError):
    """Raised when a task does not satisfy the canonical contract."""


def _schema_path_from_environment() -> Path | None:
    configured_path = os.getenv("TASK_CONTRACT_SCHEMA_PATH")

    if not configured_path:
        return None

    return Path(configured_path).expanduser().resolve()


def _find_canonical_schema_path() -> Path:
    environment_path = _schema_path_from_environment()

    if environment_path is not None:
        if environment_path.is_file():
            return environment_path

        raise TaskContractConfigurationError(
            "TASK_CONTRACT_SCHEMA_PATH does not point to a file: "
            f"{environment_path}"
        )

    module_path = Path(__file__).resolve()

    for base_path in module_path.parents:
        candidate = (
            base_path
            / "contracts"
            / "tasks"
            / "task-envelope-v1.schema.json"
        )

        if candidate.is_file():
            return candidate

    raise TaskContractConfigurationError(
        "Unable to locate contracts/tasks/"
        "task-envelope-v1.schema.json"
    )


def _load_schema() -> dict[str, Any]:
    schema_path = _find_canonical_schema_path()

    with schema_path.open(
        "r",
        encoding="utf-8",
    ) as schema_file:
        schema = json.load(schema_file)

    if not isinstance(schema, dict):
        raise TaskContractConfigurationError(
            "Canonical task schema must contain a JSON object"
        )

    Draft202012Validator.check_schema(schema)

    return schema


TASK_ENVELOPE_SCHEMA = _load_schema()

TASK_ENVELOPE_VALIDATOR = Draft202012Validator(
    TASK_ENVELOPE_SCHEMA,
    format_checker=FormatChecker(),
)


def validate_task_envelope(
    task: Any,
) -> dict[str, Any]:
    """Validate and return a canonical OpsFlow task envelope."""

    errors = sorted(
        TASK_ENVELOPE_VALIDATOR.iter_errors(task),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        first_error: ValidationError = errors[0]

        location = ".".join(
            str(part)
            for part in first_error.absolute_path
        )

        if location:
            message = (
                f"Invalid task envelope at {location}: "
                f"{first_error.message}"
            )
        else:
            message = (
                "Invalid task envelope: "
                f"{first_error.message}"
            )

        raise InvalidTaskEnvelopeError(message)

    if not isinstance(task, dict):
        raise InvalidTaskEnvelopeError(
            "Validated task envelope must be an object"
        )

    return task