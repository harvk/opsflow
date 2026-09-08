from __future__ import annotations

from collections.abc import (
    Iterator,
)

from datetime import (
    datetime,
)

import json
import logging

from typing import (
    Any,
    cast,
)

from uuid import (
    UUID,
    uuid4,
)

import pytest

from fastapi import (
    Request,
)

from app.core.security_events import (
    SecurityEventLogger,
)


# =========================================================
# TEST CONTRACT
# =========================================================


MAX_SECURITY_TEXT_LENGTH = (
    256
)


SecurityDetailValue = (
    str
    | int
    | bool
    | None
)


# =========================================================
# RECORDING LOG HANDLER
# =========================================================


class RecordingLogHandler(
    logging.Handler
):
    """
    Capture final messages emitted by SecurityEventLogger.

    The production logger serializes each event as one JSON
    object before handing it to Python logging.
    """

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.messages: list[
            str
        ] = []

    def emit(
        self,
        record: logging.LogRecord,
    ) -> None:
        self.messages.append(
            record.getMessage()
        )


# =========================================================
# FAILING LOGGER
# =========================================================


class FailingPythonLogger(
    logging.Logger
):
    """
    Simulate complete failure of the underlying logging sink.

    Security telemetry failure must never become an
    authentication/application failure.
    """

    def log(
        self,
        level: int,
        msg: object,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        del level
        del msg
        del args
        del kwargs

        raise RuntimeError(
            "Simulated security logging failure."
        )


# =========================================================
# ISOLATED LOGGER FIXTURE
# =========================================================


@pytest.fixture
def logger_harness(
) -> Iterator[
    tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ]
]:
    """
    Build an isolated real SecurityEventLogger for every
    test.

    Unique logger names prevent handler/state leakage between
    cases.
    """

    python_logger = (
        logging.getLogger(
            (
                "opsflow.security.integrity."
                f"{uuid4().hex}"
            )
        )
    )

    python_logger.handlers.clear()

    python_logger.propagate = (
        False
    )

    handler = (
        RecordingLogHandler()
    )

    python_logger.addHandler(
        handler
    )

    event_logger = (
        SecurityEventLogger(
            hmac_key=(
                "security-event-integrity-"
                "test-hmac-key"
            ),
            logger=(
                python_logger
            ),
        )
    )

    try:
        yield (
            event_logger,
            handler,
        )

    finally:
        python_logger.removeHandler(
            handler
        )

        handler.close()

        python_logger.handlers.clear()


# =========================================================
# REQUEST FACTORY
# =========================================================


def build_request(
    *,
    path: str = (
        "/api/v1/auth/token"
    ),
    forwarded_for: str | None = None,
) -> Request:
    """
    Construct a minimal ASGI request.

    The ASGI client address is deliberately fixed to
    127.0.0.1.

    An optional X-Forwarded-For header lets us verify that
    SecurityEventLogger does not trust the header directly.
    """

    headers: list[
        tuple[
            bytes,
            bytes,
        ]
    ] = [
        (
            b"content-type",
            b"application/json",
        ),
    ]

    if (
        forwarded_for
        is not None
    ):
        headers.append(
            (
                b"x-forwarded-for",
                forwarded_for.encode(
                    "utf-8"
                ),
            )
        )

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": path,
        "raw_path": (
            path.encode(
                "utf-8"
            )
        ),
        "query_string": b"",
        "headers": headers,
        "client": (
            "127.0.0.1",
            50000,
        ),
        "server": (
            "testserver",
            443,
        ),
    }

    return (
        Request(
            scope
        )
    )


# =========================================================
# PAYLOAD HELPERS
# =========================================================


def require_payload(
    handler: RecordingLogHandler,
    *,
    index: int = 0,
) -> dict[
    str,
    Any,
]:
    """
    Parse one emitted security-event JSON document.
    """

    assert (
        len(
            handler.messages
        )
        > index
    )

    parsed = (
        json.loads(
            handler.messages[
                index
            ]
        )
    )

    assert isinstance(
        parsed,
        dict,
    )

    return cast(
        dict[
            str,
            Any,
        ],
        parsed,
    )


def require_details(
    payload: dict[
        str,
        Any,
    ],
) -> dict[
    str,
    Any,
]:
    details = (
        payload.get(
            "details"
        )
    )

    assert isinstance(
        details,
        dict,
    )

    return cast(
        dict[
            str,
            Any,
        ],
        details,
    )


def assert_no_log_control_characters(
    value: str,
) -> None:
    """
    Structured fields should not retain literal log-control
    characters after sanitization.
    """

    assert (
        "\r"
        not in value
    )

    assert (
        "\n"
        not in value
    )

    assert (
        "\t"
        not in value
    )


# =========================================================
# CONSTRUCTOR SAFETY
# =========================================================


def test_security_event_logger_requires_hmac_key(
) -> None:
    """
    Account pseudonymization must never silently run without
    its keyed secret.
    """

    with pytest.raises(
        ValueError,
        match=(
            "HMAC key"
        ),
    ):
        SecurityEventLogger(
            hmac_key="",
        )


# =========================================================
# LOG-INJECTION DEFENSE
# =========================================================


def test_security_event_logger_removes_control_characters_from_text_fields(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    CR/LF/tab characters supplied through attacker-influenced
    metadata must not survive into structured field values.

    This prevents confusing or forged-looking multi-line log
    records.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    details: dict[
        str,
        SecurityDetailValue,
    ] = {
        (
            "safe\r\n\t"
            "detail_key"
        ): (
            "safe\r\n\t"
            "detail_value"
        ),
    }

    event_logger.emit(
        event=(
            "auth.test\r\n"
            "forged-event"
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        user_id=(
            "user\r\n"
            "forged-user"
        ),
        reason=(
            "failure\r\n\t"
            "forged-reason"
        ),
        details=(
            details
        ),
    )

    payload = (
        require_payload(
            handler
        )
    )

    assert_no_log_control_characters(
        cast(
            str,
            payload[
                "event"
            ],
        )
    )

    assert_no_log_control_characters(
        cast(
            str,
            payload[
                "user_id"
            ],
        )
    )

    assert_no_log_control_characters(
        cast(
            str,
            payload[
                "reason"
            ],
        )
    )

    logged_details = (
        require_details(
            payload
        )
    )

    assert (
        len(
            logged_details
        )
        == 1
    )

    detail_key = (
        next(
            iter(
                logged_details
            )
        )
    )

    detail_value = (
        logged_details[
            detail_key
        ]
    )

    assert isinstance(
        detail_value,
        str,
    )

    assert_no_log_control_characters(
        detail_key
    )

    assert_no_log_control_characters(
        detail_value
    )

    # Sanitization replaces the control characters rather
    # than destroying the useful surrounding metadata.

    assert (
        "forged-event"
        in payload[
            "event"
        ]
    )

    assert (
        "forged-reason"
        in payload[
            "reason"
        ]
    )


# =========================================================
# SIZE BOUNDARIES
# =========================================================


def test_security_event_logger_bounds_attacker_controlled_text_fields(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Large attacker-controlled values must not create
    unbounded structured security-event fields.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    long_event = (
        "event-"
        + (
            "E"
            * 1000
        )
    )

    long_reason = (
        "reason-"
        + (
            "R"
            * 1000
        )
    )

    long_user_id = (
        "user-"
        + (
            "U"
            * 1000
        )
    )

    long_detail_key = (
        "safe_metadata_"
        + (
            "K"
            * 1000
        )
    )

    long_detail_value = (
        "safe-value-"
        + (
            "V"
            * 1000
        )
    )

    details: dict[
        str,
        SecurityDetailValue,
    ] = {
        long_detail_key: (
            long_detail_value
        ),
    }

    event_logger.emit(
        event=(
            long_event
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        user_id=(
            long_user_id
        ),
        reason=(
            long_reason
        ),
        details=(
            details
        ),
    )

    payload = (
        require_payload(
            handler
        )
    )

    assert (
        len(
            cast(
                str,
                payload[
                    "event"
                ],
            )
        )
        == MAX_SECURITY_TEXT_LENGTH
    )

    assert (
        len(
            cast(
                str,
                payload[
                    "reason"
                ],
            )
        )
        == MAX_SECURITY_TEXT_LENGTH
    )

    assert (
        len(
            cast(
                str,
                payload[
                    "user_id"
                ],
            )
        )
        == MAX_SECURITY_TEXT_LENGTH
    )

    logged_details = (
        require_details(
            payload
        )
    )

    assert (
        len(
            logged_details
        )
        == 1
    )

    detail_key = (
        next(
            iter(
                logged_details
            )
        )
    )

    detail_value = (
        logged_details[
            detail_key
        ]
    )

    assert (
        len(
            detail_key
        )
        == MAX_SECURITY_TEXT_LENGTH
    )

    assert isinstance(
        detail_value,
        str,
    )

    assert (
        len(
            detail_value
        )
        == MAX_SECURITY_TEXT_LENGTH
    )


# =========================================================
# EVENT METADATA INTEGRITY
# =========================================================


def test_security_event_logger_emits_valid_event_identity_and_timestamp(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Every emitted event must carry:

        a valid UUID event id
        an offset-aware timestamp
        the requested severity
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    event_logger.emit(
        event=(
            "auth.test.metadata"
        ),
        outcome=(
            "blocked"
        ),
        level=(
            logging.WARNING
        ),
        reason=(
            "metadata_test"
        ),
    )

    payload = (
        require_payload(
            handler
        )
    )

    event_id = (
        UUID(
            cast(
                str,
                payload[
                    "event_id"
                ],
            )
        )
    )

    assert isinstance(
        event_id,
        UUID,
    )

    occurred_at = (
        datetime.fromisoformat(
            cast(
                str,
                payload[
                    "occurred_at"
                ],
            )
        )
    )

    assert (
        occurred_at.tzinfo
        is not None
    )

    assert (
        occurred_at.utcoffset()
        is not None
    )

    assert (
        payload[
            "severity"
        ]
        == "warning"
    )

    assert (
        payload[
            "outcome"
        ]
        == "blocked"
    )


# =========================================================
# UNIQUE EVENT IDS
# =========================================================


def test_security_event_logger_generates_unique_event_ids(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Separate security events must remain independently
    traceable.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    event_logger.emit(
        event=(
            "auth.test.first"
        ),
        outcome=(
            "success"
        ),
        level=(
            logging.INFO
        ),
    )

    event_logger.emit(
        event=(
            "auth.test.second"
        ),
        outcome=(
            "success"
        ),
        level=(
            logging.INFO
        ),
    )

    assert (
        len(
            handler.messages
        )
        == 2
    )

    first_payload = (
        require_payload(
            handler,
            index=0,
        )
    )

    second_payload = (
        require_payload(
            handler,
            index=1,
        )
    )

    assert (
        first_payload[
            "event_id"
        ]
        != second_payload[
            "event_id"
        ]
    )


# =========================================================
# ACCOUNT FINGERPRINT NORMALIZATION
# =========================================================


def test_account_fingerprint_normalizes_case_and_whitespace(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Equivalent account identifiers must map to the same
    pseudonymous correlation value.
    """

    (
        event_logger,
        _,
    ) = (
        logger_harness
    )

    canonical = (
        event_logger
        .account_fingerprint(
            "user@example.com"
        )
    )

    uppercase = (
        event_logger
        .account_fingerprint(
            "USER@EXAMPLE.COM"
        )
    )

    padded = (
        event_logger
        .account_fingerprint(
            "  user@example.com  "
        )
    )

    assert (
        canonical
        == uppercase
    )

    assert (
        canonical
        == padded
    )

    assert (
        len(
            canonical
        )
        == 64
    )


def test_account_fingerprint_changes_for_different_accounts(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Distinct accounts must not collapse to one correlation
    value.
    """

    (
        event_logger,
        _,
    ) = (
        logger_harness
    )

    first = (
        event_logger
        .account_fingerprint(
            "first@example.com"
        )
    )

    second = (
        event_logger
        .account_fingerprint(
            "second@example.com"
        )
    )

    assert (
        first
        != second
    )


def test_account_fingerprint_depends_on_hmac_key(
) -> None:
    """
    Account fingerprints must be keyed pseudonyms rather than
    unkeyed hashes that could be precomputed externally.
    """

    first_logger = (
        SecurityEventLogger(
            hmac_key=(
                "first-test-hmac-key"
            ),
            logger=(
                logging.getLogger(
                    (
                        "opsflow.security."
                        "fingerprint.first."
                        f"{uuid4().hex}"
                    )
                )
            ),
        )
    )

    second_logger = (
        SecurityEventLogger(
            hmac_key=(
                "second-test-hmac-key"
            ),
            logger=(
                logging.getLogger(
                    (
                        "opsflow.security."
                        "fingerprint.second."
                        f"{uuid4().hex}"
                    )
                )
            ),
        )
    )

    account = (
        "user@example.com"
    )

    assert (
        first_logger
        .account_fingerprint(
            account
        )
        != second_logger
        .account_fingerprint(
            account
        )
    )


# =========================================================
# CLIENT ADDRESS TRUST BOUNDARY
# =========================================================


def test_security_event_logger_does_not_trust_x_forwarded_for_directly(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    X-Forwarded-For is attacker-controlled unless a trusted
    proxy layer has already validated it.

    SecurityEventLogger must use request.client rather than
    reading the forwarded header directly.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    request = (
        build_request(
            forwarded_for=(
                "203.0.113.250"
            ),
        )
    )

    event_logger.emit(
        event=(
            "auth.test.client"
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        request=(
            request
        ),
    )

    payload = (
        require_payload(
            handler
        )
    )

    assert (
        payload[
            "client_address"
        ]
        == "127.0.0.1"
    )

    assert (
        "203.0.113.250"
        not in handler.messages[
            0
        ]
    )


# =========================================================
# LOGGING FAILURE ISOLATION
# =========================================================


def test_security_event_logging_failure_never_escapes_emit(
) -> None:
    """
    Security telemetry is important, but a failed logging
    backend must not turn authentication into a 500-class
    application failure.

    emit() must swallow logging subsystem exceptions.
    """

    failing_logger = (
        FailingPythonLogger(
            (
                "opsflow.security."
                "failing-test"
            )
        )
    )

    event_logger = (
        SecurityEventLogger(
            hmac_key=(
                "security-event-failure-"
                "test-hmac-key"
            ),
            logger=(
                failing_logger
            ),
        )
    )

    result = (
        event_logger.emit(
            event=(
                "auth.login.failed"
            ),
            outcome=(
                "failure"
            ),
            level=(
                logging.WARNING
            ),
            reason=(
                "invalid_credentials"
            ),
            details={
                "safe_counter": (
                    1
                ),
            },
        )
    )

    assert (
        result
        is None
    )