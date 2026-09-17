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