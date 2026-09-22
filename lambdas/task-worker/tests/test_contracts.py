from __future__ import annotations

import json
from pathlib import Path

import pytest

from task_worker.contracts import (
    InvalidTaskEnvelopeError,
    validate_task_envelope,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

FIXTURES_DIRECTORY = (
    REPOSITORY_ROOT
    / "contracts"
    / "tasks"
    / "fixtures"
)


def load_fixture(
    filename: str,
) -> dict[str, object]:
    with (
        FIXTURES_DIRECTORY
        / filename
    ).open(
        "r",
        encoding="utf-8",
    ) as fixture_file:
        return json.load(fixture_file)


def test_accepts_canonical_valid_fixture() -> None:
    task = load_fixture(
        "valid-task-v1.json",
    )

    result = validate_task_envelope(task)

    assert result == task


def test_rejects_missing_idempotency_key() -> None:
    task = load_fixture(
        "invalid-task-missing-idempotency-v1.json",
    )

    with pytest.raises(
        InvalidTaskEnvelopeError,
        match="idempotency_key",
    ):
        validate_task_envelope(task)


def test_accepts_non_uuid_correlation_id(
) -> None:
    task = load_fixture(
        "valid-task-v1.json"
    )

    task[
        "correlation_id"
    ] = (
        "phase-11-5e10-"
        "20260919T151359Z"
    )

    assert (
        validate_task_envelope(
            task
        )
        == task
    )


def test_accepts_non_uuid_causation_id(
) -> None:
    task = load_fixture(
        "valid-task-v1.json"
    )

    task[
        "causation_id"
    ] = (
        "incident-created:"
        "11111111-1111-4111-8111-111111111111"
    )

    assert (
        validate_task_envelope(
            task
        )
        == task
    )


def test_rejects_empty_correlation_id(
) -> None:
    task = load_fixture(
        "valid-task-v1.json"
    )

    task[
        "correlation_id"
    ] = ""

    with pytest.raises(
        InvalidTaskEnvelopeError,
        match=(
            "correlation_id"
        ),
    ):
        validate_task_envelope(
            task
        )
