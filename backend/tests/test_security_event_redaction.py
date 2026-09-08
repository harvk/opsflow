from __future__ import annotations

from collections.abc import (
    Iterator,
)

import json
import logging

from typing import (
    Any,
    cast,
)

from uuid import (
    uuid4,
)

import pytest

from fastapi import (
    Request,
)

from app.core.security_events import (
    SecurityDetailValue,
    SecurityEventLogger,
)


# =========================================================
# DISTINCTIVE TEST SECRETS
# =========================================================


PASSWORD_SECRET = (
    "SECRET-PASSWORD-"
    "DO-NOT-LOG-10001!"
)

NEW_PASSWORD_SECRET = (
    "SECRET-NEW-PASSWORD-"
    "DO-NOT-LOG-10002!"
)

ACCESS_TOKEN_SECRET = (
    "SECRET-ACCESS-TOKEN-"
    "DO-NOT-LOG-10003"
)

REFRESH_TOKEN_SECRET = (
    "SECRET-REFRESH-TOKEN-"
    "DO-NOT-LOG-10004"
)

RESET_TOKEN_SECRET = (
    "SECRET-RESET-TOKEN-"
    "DO-NOT-LOG-10005"
)

CSRF_TOKEN_SECRET = (
    "SECRET-CSRF-TOKEN-"
    "DO-NOT-LOG-10006"
)

REAUTH_TOKEN_SECRET = (
    "SECRET-REAUTH-TOKEN-"
    "DO-NOT-LOG-10007"
)

COOKIE_SECRET = (
    "SECRET-COOKIE-"
    "DO-NOT-LOG-10008"
)

API_KEY_SECRET = (
    "SECRET-API-KEY-"
    "DO-NOT-LOG-10009"
)

CLIENT_SECRET = (
    "SECRET-CLIENT-SECRET-"
    "DO-NOT-LOG-10010"
)

PRIVATE_KEY_SECRET = (
    "SECRET-PRIVATE-KEY-"
    "DO-NOT-LOG-10011"
)

SIGNING_KEY_SECRET = (
    "SECRET-SIGNING-KEY-"
    "DO-NOT-LOG-10012"
)


ALL_TEST_SECRETS = (
    PASSWORD_SECRET,
    NEW_PASSWORD_SECRET,
    ACCESS_TOKEN_SECRET,
    REFRESH_TOKEN_SECRET,
    RESET_TOKEN_SECRET,
    CSRF_TOKEN_SECRET,
    REAUTH_TOKEN_SECRET,
    COOKIE_SECRET,
    API_KEY_SECRET,
    CLIENT_SECRET,
    PRIVATE_KEY_SECRET,
    SIGNING_KEY_SECRET,
)


# =========================================================
# RECORDING LOG HANDLER
# =========================================================


class RecordingLogHandler(
    logging.Handler
):
    """
    Capture the final formatted message emitted by the real
    SecurityEventLogger.

    Because SecurityEventLogger serializes its structured
    payload before calling Python logging, each captured
    message should be one JSON document.
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
# TEST LOGGER FIXTURE
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
    Construct an isolated real SecurityEventLogger.

    A unique Python logger prevents handlers or state from
    leaking between test cases.
    """

    python_logger = (
        logging.getLogger(
            (
                "opsflow.security.test."
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
                "security-event-redaction-"
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


def build_sensitive_request(
) -> Request:
    """
    Construct a Request containing credentials in locations
    that security telemetry must never serialize:

        Authorization header
        Cookie header
        query string

    Safe request metadata such as method, route path, and
    client address may still be recorded.
    """

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": (
            "/api/v1/auth/"
            "password-reset/confirm"
        ),
        "raw_path": (
            b"/api/v1/auth/"
            b"password-reset/confirm"
        ),
        "query_string": (
            (
                "token="
                + RESET_TOKEN_SECRET
            )
            .encode(
                "utf-8"
            )
        ),
        "headers": [
            (
                b"authorization",
                (
                    "Bearer "
                    + ACCESS_TOKEN_SECRET
                )
                .encode(
                    "utf-8"
                ),
            ),
            (
                b"cookie",
                (
                    "refresh_token="
                    + REFRESH_TOKEN_SECRET
                    + "; csrf_token="
                    + CSRF_TOKEN_SECRET
                    + "; test_cookie="
                    + COOKIE_SECRET
                )
                .encode(
                    "utf-8"
                ),
            ),
            (
                b"content-type",
                b"application/json",
            ),
        ],
        "client": (
            "127.0.0.1",
            54321,
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


def require_single_payload(
    handler: RecordingLogHandler,
) -> dict[
    str,
    Any,
]:
    """
    Require exactly one JSON security event and return its
    parsed payload.
    """

    assert (
        len(
            handler.messages
        )
        == 1
    )

    raw_message = (
        handler.messages[
            0
        ]
    )

    parsed = (
        json.loads(
            raw_message
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
    """
    Require a structured details object in the event.
    """

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


def assert_no_test_secrets(
    serialized: str,
) -> None:
    for secret in (
        ALL_TEST_SECRETS
    ):
        assert (
            secret
            not in serialized
        ), (
            "A raw authentication secret reached the "
            "security-event logging sink: "
            f"{secret!r}"
        )


# =========================================================
# SENSITIVE FIELD REDACTION
# =========================================================


@pytest.mark.parametrize(
    (
        "field_name",
        "secret",
    ),
    [
        (
            "password",
            PASSWORD_SECRET,
        ),
        (
            "Password",
            PASSWORD_SECRET,
        ),
        (
            "new_password",
            NEW_PASSWORD_SECRET,
        ),
        (
            "new-password",
            NEW_PASSWORD_SECRET,
        ),
        (
            "token",
            RESET_TOKEN_SECRET,
        ),
        (
            "accessToken",
            ACCESS_TOKEN_SECRET,
        ),
        (
            "REFRESH_TOKEN",
            REFRESH_TOKEN_SECRET,
        ),
        (
            "reset-token",
            RESET_TOKEN_SECRET,
        ),
        (
            "csrfToken",
            CSRF_TOKEN_SECRET,
        ),
        (
            "reauth_token",
            REAUTH_TOKEN_SECRET,
        ),
        (
            "Authorization",
            ACCESS_TOKEN_SECRET,
        ),
        (
            "Cookie",
            COOKIE_SECRET,
        ),
        (
            "api-key",
            API_KEY_SECRET,
        ),
        (
            "clientSecret",
            CLIENT_SECRET,
        ),
        (
            "private_key",
            PRIVATE_KEY_SECRET,
        ),
        (
            "signingKey",
            SIGNING_KEY_SECRET,
        ),
        (
            "bearer",
            ACCESS_TOKEN_SECRET,
        ),
        (
            "credential",
            RESET_TOKEN_SECRET,
        ),
    ],
)
def test_security_event_logger_never_serializes_known_secret_fields(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
    field_name: str,
    secret: str,
) -> None:
    """
    Sensitive field matching must be resilient to common
    casing and punctuation variations.
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
        field_name: (
            secret
        ),
        "safe_counter": (
            1
        ),
    }

    event_logger.emit(
        event=(
            "auth.test.secret_field"
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        reason=(
            "secret_field_test"
        ),
        details=(
            details
        ),
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    logged_details = (
        require_details(
            payload
        )
    )

    assert (
        logged_details[
            field_name
        ]
        == (
            SecurityEventLogger
            .REDACTED_DETAIL_VALUE
        )
    )

    assert (
        logged_details[
            "safe_counter"
        ]
        == 1
    )

    assert (
        secret
        not in handler.messages[
            0
        ]
    )


# =========================================================
# MULTIPLE SECRET VALUES
# =========================================================


def test_security_event_logger_redacts_multiple_sensitive_scalar_details(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Several accidental credential fields in the same event
    must all be redacted without destroying safe telemetry.
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
        "password": (
            PASSWORD_SECRET
        ),
        "new_password": (
            NEW_PASSWORD_SECRET
        ),
        "access_token": (
            ACCESS_TOKEN_SECRET
        ),
        "refresh_token": (
            REFRESH_TOKEN_SECRET
        ),
        "reset_token": (
            RESET_TOKEN_SECRET
        ),
        "csrf_token": (
            CSRF_TOKEN_SECRET
        ),
        "reauth_token": (
            REAUTH_TOKEN_SECRET
        ),
        "api_key": (
            API_KEY_SECRET
        ),
        "client_secret": (
            CLIENT_SECRET
        ),
        "safe_counter": (
            42
        ),
        "safe_flag": (
            True
        ),
        "safe_value": (
            "preserve-me"
        ),
    }

    event_logger.emit(
        event=(
            "auth.test.redaction"
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        reason=(
            "redaction_test"
        ),
        details=(
            details
        ),
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    logged_details = (
        require_details(
            payload
        )
    )

    for sensitive_key in (
        "password",
        "new_password",
        "access_token",
        "refresh_token",
        "reset_token",
        "csrf_token",
        "reauth_token",
        "api_key",
        "client_secret",
    ):
        assert (
            logged_details[
                sensitive_key
            ]
            == (
                SecurityEventLogger
                .REDACTED_DETAIL_VALUE
            )
        )

    assert_no_test_secrets(
        handler.messages[
            0
        ]
    )

    assert (
        logged_details[
            "safe_counter"
        ]
        == 42
    )

    assert (
        logged_details[
            "safe_flag"
        ]
        is True
    )

    assert (
        logged_details[
            "safe_value"
        ]
        == "preserve-me"
    )


# =========================================================
# REQUEST MATERIAL NON-DISCLOSURE
# =========================================================


def test_security_event_logger_does_not_serialize_sensitive_request_material(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Request metadata must be explicitly selected.

    Headers, cookies, and the query string must not be dumped
    into the structured security event.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    request = (
        build_sensitive_request()
    )

    event_logger.emit(
        event=(
            "auth.test.request_metadata"
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
        reason=(
            "request_metadata_test"
        ),
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    assert_no_test_secrets(
        handler.messages[
            0
        ]
    )

    assert (
        payload[
            "http_method"
        ]
        == "POST"
    )

    assert (
        payload[
            "http_path"
        ]
        == (
            "/api/v1/auth/"
            "password-reset/confirm"
        )
    )

    assert (
        payload[
            "client_address"
        ]
        == "127.0.0.1"
    )

    assert (
        "query_string"
        not in payload
    )

    assert (
        "headers"
        not in payload
    )

    assert (
        "authorization"
        not in payload
    )

    assert (
        "cookie"
        not in payload
    )


# =========================================================
# SAFE OPERATIONAL DETAILS
# =========================================================


def test_security_event_logger_preserves_existing_safe_operational_details(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Redaction must not damage the safe scalar telemetry
    already emitted by authentication routes.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    expected_details: dict[
        str,
        SecurityDetailValue,
    ] = {
        "sessions_revoked": (
            3
        ),
        "retry_after_seconds": (
            60
        ),
        "refresh_rotated": (
            True
        ),
        "session_revoked": (
            False
        ),
        "optional_value": (
            None
        ),
    }

    event_logger.emit(
        event=(
            "auth.test.safe_details"
        ),
        outcome=(
            "success"
        ),
        level=(
            logging.INFO
        ),
        reason=(
            "safe_details_test"
        ),
        details=(
            expected_details
        ),
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    logged_details = (
        require_details(
            payload
        )
    )

    assert (
        logged_details
        == expected_details
    )


# =========================================================
# CORE EVENT METADATA
# =========================================================


def test_security_event_logger_preserves_core_security_metadata(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Defensive redaction must not make security events
    operationally useless.
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
            "test_reason"
        ),
        details={
            "safe_value": (
                "visible"
            ),
        },
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    assert (
        payload[
            "event"
        ]
        == "auth.test.metadata"
    )

    assert (
        payload[
            "outcome"
        ]
        == "blocked"
    )

    assert (
        payload[
            "reason"
        ]
        == "test_reason"
    )

    assert (
        payload[
            "severity"
        ]
        == "warning"
    )

    logged_details = (
        require_details(
            payload
        )
    )

    assert (
        logged_details[
            "safe_value"
        ]
        == "visible"
    )


# =========================================================
# ACCOUNT IDENTIFIER PSEUDONYMIZATION
# =========================================================


def test_security_event_logger_pseudonymizes_account_identifier(
    logger_harness: tuple[
        SecurityEventLogger,
        RecordingLogHandler,
    ],
) -> None:
    """
    Account identifiers should remain correlatable without
    storing the submitted identifier itself.
    """

    (
        event_logger,
        handler,
    ) = (
        logger_harness
    )

    account_identifier = (
        " Sensitive.User@Example.com "
    )

    event_logger.emit(
        event=(
            "auth.test.account"
        ),
        outcome=(
            "failure"
        ),
        level=(
            logging.WARNING
        ),
        account_identifier=(
            account_identifier
        ),
        reason=(
            "test_reason"
        ),
    )

    payload = (
        require_single_payload(
            handler
        )
    )

    serialized = (
        handler.messages[
            0
        ]
    )

    assert (
        "Sensitive.User@Example.com"
        not in serialized
    )

    assert (
        "account_identifier"
        not in payload
    )

    assert (
        payload[
            "account_fingerprint"
        ]
        == (
            event_logger
            .account_fingerprint(
                account_identifier
            )
        )
    )