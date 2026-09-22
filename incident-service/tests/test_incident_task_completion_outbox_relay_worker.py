from __future__ import annotations

import pytest

from app.workers.incident_task_completion_outbox_relay import (
    CompletionOutboxRelaySettings,
    load_completion_outbox_relay_settings,
)


def test_loads_completion_relay_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "REALTIME_NOTIFICATION_QUEUE_URL",
        (
            "https://sqs.us-east-1.amazonaws.com/"
            "123456789012/"
            "opsflow-dev-realtime-notification-queue"
        ),
    )

    monkeypatch.setenv(
        (
            "INCIDENT_TASK_COMPLETION_"
            "OUTBOX_RELAY_POLL_SECONDS"
        ),
        "3.5",
    )

    monkeypatch.setenv(
        (
            "INCIDENT_TASK_COMPLETION_"
            "OUTBOX_RELAY_RETRY_SECONDS"
        ),
        "30",
    )

    settings = (
        load_completion_outbox_relay_settings()
    )

    assert settings == (
        CompletionOutboxRelaySettings(
            realtime_notification_queue_url=(
                "https://sqs.us-east-1.amazonaws.com/"
                "123456789012/"
                "opsflow-dev-realtime-notification-queue"
            ),
            poll_seconds=3.5,
            retry_seconds=30,
        )
    )


def test_missing_notification_queue_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "REALTIME_NOTIFICATION_QUEUE_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "REALTIME_NOTIFICATION_QUEUE_URL "
            "must be configured"
        ),
    ):
        (
            load_completion_outbox_relay_settings()
        )


@pytest.mark.parametrize(
    (
        "name",
        "value",
        "message",
    ),
    [
        (
            (
                "INCIDENT_TASK_COMPLETION_"
                "OUTBOX_RELAY_POLL_SECONDS"
            ),
            "0",
            "greater than zero",
        ),
        (
            (
                "INCIDENT_TASK_COMPLETION_"
                "OUTBOX_RELAY_POLL_SECONDS"
            ),
            "not-a-number",
            "must be numeric",
        ),
        (
            (
                "INCIDENT_TASK_COMPLETION_"
                "OUTBOX_RELAY_RETRY_SECONDS"
            ),
            "0",
            "greater than zero",
        ),
        (
            (
                "INCIDENT_TASK_COMPLETION_"
                "OUTBOX_RELAY_RETRY_SECONDS"
            ),
            "not-an-integer",
            "must be a whole number",
        ),
    ],
)
def test_invalid_completion_relay_timing_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(
        "REALTIME_NOTIFICATION_QUEUE_URL",
        "https://example.invalid/queue",
    )

    monkeypatch.setenv(
        name,
        value,
    )

    with pytest.raises(
        RuntimeError,
        match=message,
    ):
        (
            load_completion_outbox_relay_settings()
        )
