import json
import logging

from app.core.security_events import (
    SecurityEventLogger,
)


class RecordingLogger:
    def __init__(
        self,
    ) -> None:
        self.records: list[
            tuple[
                int,
                str,
            ]
        ] = []

    def setLevel(
        self,
        level: int,
    ) -> None:
        pass

    def log(
        self,
        level: int,
        message: str,
    ) -> None:
        self.records.append(
            (
                level,
                message,
            )
        )


def create_security_logger(
) -> tuple[
    SecurityEventLogger,
    RecordingLogger,
]:
    recording_logger = (
        RecordingLogger()
    )

    security_logger = (
        SecurityEventLogger(
            hmac_key=(
                "test-security-event-key"
            ),
            logger=recording_logger,  # type: ignore[arg-type]
        )
    )

    return (
        security_logger,
        recording_logger,
    )


def test_account_fingerprint_is_stable(
) -> None:
    security_logger, _ = (
        create_security_logger()
    )

    first = (
        security_logger
        .account_fingerprint(
            "USER@example.com"
        )
    )

    second = (
        security_logger
        .account_fingerprint(
            "  user@example.com  "
        )
    )

    assert first == second


def test_different_accounts_have_different_fingerprints(
) -> None:
    security_logger, _ = (
        create_security_logger()
    )

    first = (
        security_logger
        .account_fingerprint(
            "first@example.com"
        )
    )

    second = (
        security_logger
        .account_fingerprint(
            "second@example.com"
        )
    )

    assert first != second


def test_security_event_is_structured_json(
) -> None:
    security_logger, recording = (
        create_security_logger()
    )

    security_logger.emit(
        event="auth.login.failed",
        outcome="failure",
        level=logging.WARNING,
        account_identifier=(
            "admin@example.com"
        ),
        reason="invalid_credentials",
    )

    assert (
        len(recording.records)
        == 1
    )

    level, message = (
        recording.records[0]
    )

    assert (
        level
        == logging.WARNING
    )

    payload = json.loads(
        message
    )

    assert (
        payload["event"]
        == "auth.login.failed"
    )

    assert (
        payload["outcome"]
        == "failure"
    )

    assert (
        payload["severity"]
        == "warning"
    )

    assert (
        payload["reason"]
        == "invalid_credentials"
    )

    assert (
        payload[
            "account_fingerprint"
        ]
    )

    assert payload["event_id"]
    assert payload["occurred_at"]


def test_raw_account_identifier_is_not_logged(
) -> None:
    security_logger, recording = (
        create_security_logger()
    )

    security_logger.emit(
        event="auth.login.failed",
        outcome="failure",
        level=logging.WARNING,
        account_identifier=(
            "secret-user@example.com"
        ),
        reason="invalid_credentials",
    )

    _, message = (
        recording.records[0]
    )

    assert (
        "secret-user@example.com"
        not in message
    )


def test_log_control_characters_are_sanitized(
) -> None:
    security_logger, recording = (
        create_security_logger()
    )

    security_logger.emit(
        event="test.event",
        outcome="failure",
        level=logging.WARNING,
        reason=(
            "bad\r\n"
            "FORGED LOG ENTRY"
        ),
    )

    _, message = (
        recording.records[0]
    )

    payload = json.loads(
        message
    )

    assert (
        "\r"
        not in payload["reason"]
    )

    assert (
        "\n"
        not in payload["reason"]
    )


def test_logging_failure_does_not_break_application_flow(
) -> None:
    class BrokenLogger:
        def setLevel(
            self,
            level: int,
        ) -> None:
            pass

        def log(
            self,
            level: int,
            message: str,
        ) -> None:
            raise RuntimeError(
                "logging unavailable"
            )

    security_logger = (
        SecurityEventLogger(
            hmac_key=(
                "test-security-event-key"
            ),
            logger=BrokenLogger(),  # type: ignore[arg-type]
        )
    )

    # The absence of an exception is the assertion.
    security_logger.emit(
        event="auth.login.failed",
        outcome="failure",
        level=logging.WARNING,
        account_identifier=(
            "user@example.com"
        ),
        reason="invalid_credentials",
    )