from __future__ import annotations

from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Any,
)

from uuid import (
    uuid4,
)

from fastapi import (
    Request,
)

from fastapi.testclient import (
    TestClient,
)

import app.api.dependencies as dependency_module

import app.api.routes.auth as auth_route_module

from app.api.dependencies import (
    get_login_throttle,
    get_password_reset_throttle,
)


# =========================================================
# TEST CREDENTIALS
# =========================================================
#
# These values are intentionally distinctive.
#
# If one appears in:
#
#     a security-event payload
#     an error response
#
# the corresponding assertion should fail loudly.
# =========================================================


LOGIN_PASSWORD = (
    "DO-NOT-LOG-LOGIN-PASSWORD-90210!"
)

RESET_TOKEN = (
    "DO-NOT-LOG-RESET-TOKEN-"
    "0123456789abcdef"
    "0123456789abcdef"
)

RESET_PASSWORD = (
    "DO-NOT-LOG-RESET-PASSWORD-24680!"
)

ACCESS_TOKEN = (
    "DO-NOT-LOG-ACCESS-BEARER-"
    "0123456789abcdef"
    "0123456789abcdef"
)


# =========================================================
# RECORDED SECURITY EVENT
# =========================================================


@dataclass(
    slots=True,
)
class RecordedSecurityEvent:
    event: str

    outcome: str

    reason: str | None

    method: str | None

    path: str | None

    user_id: str | None

    account_identifier: (
        str | None
    )

    details: (
        dict[
            str,
            Any,
        ]
        | None
    )


# =========================================================
# SECURITY EVENT RECORDER
# =========================================================


@dataclass(
    slots=True,
)
class RecordingSecurityEventLogger:
    """
    Test double for the security-event boundary.

    The HTTP routes remain real.

    Instead of writing the event to the application's real
    logging sink, this recorder captures only the explicit
    values handed to security_event_logger.emit().

    The Request itself is not retained.

    This lets the suite determine whether authentication code
    explicitly passes a raw credential into the structured
    security-event boundary.
    """

    events: list[
        RecordedSecurityEvent
    ] = field(
        default_factory=list
    )

    def emit(
        self,
        *,
        event: str,
        outcome: str,
        level: int,
        request: (
            Request | None
        ) = None,
        user_id: Any = None,
        account_identifier: (
            str | None
        ) = None,
        reason: (
            str | None
        ) = None,
        details: (
            dict[
                str,
                Any,
            ]
            | None
        ) = None,
        **_: Any,
    ) -> None:
        """
        Capture safe event metadata.

        The logging level is accepted because production
        callers supply it, but it is irrelevant to credential
        disclosure testing.
        """

        del level

        method: (
            str | None
        ) = None

        path: (
            str | None
        ) = None

        if (
            request
            is not None
        ):
            method = (
                request.method
            )

            path = (
                request.url.path
            )

        normalized_user_id = (
            None
            if user_id
            is None
            else str(
                user_id
            )
        )

        self.events.append(
            RecordedSecurityEvent(
                event=(
                    event
                ),
                outcome=(
                    outcome
                ),
                reason=(
                    reason
                ),
                method=(
                    method
                ),
                path=(
                    path
                ),
                user_id=(
                    normalized_user_id
                ),
                account_identifier=(
                    account_identifier
                ),
                details=(
                    details
                ),
            )
        )


# =========================================================
# EVENT SEARCH
# =========================================================


def require_event(
    recorder: (
        RecordingSecurityEventLogger
    ),
    event_name: str,
) -> RecordedSecurityEvent:
    """
    Require exactly one captured event with the supplied
    event name.
    """

    matches = [
        event
        for event
        in recorder.events
        if (
            event.event
            == event_name
        )
    ]

    captured_event_names = [
        event.event
        for event
        in recorder.events
    ]

    assert (
        len(
            matches
        )
        == 1
    ), (
        f"Expected exactly one "
        f"{event_name!r} event, "
        f"but found {len(matches)}. "
        f"Captured events: "
        f"{captured_event_names!r}"
    )

    return (
        matches[
            0
        ]
    )


# =========================================================
# EVENT SERIALIZATION
# =========================================================


def event_text(
    event: RecordedSecurityEvent,
) -> str:
    """
    Produce a searchable representation of the explicit
    structured event payload.

    The Request object itself is deliberately excluded.
    """

    return repr(
        {
            "event": (
                event.event
            ),
            "outcome": (
                event.outcome
            ),
            "reason": (
                event.reason
            ),
            "method": (
                event.method
            ),
            "path": (
                event.path
            ),
            "user_id": (
                event.user_id
            ),
            "account_identifier": (
                event
                .account_identifier
            ),
            "details": (
                event.details
            ),
        }
    )


# =========================================================
# LOGIN FAILURE
# =========================================================


def test_failed_login_does_not_send_password_to_security_event_logger(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    A failed login may create a security event.

    The submitted account identifier may be recorded for
    abuse correlation.

    The submitted password must never cross the structured
    logging boundary.
    """

    recorder = (
        RecordingSecurityEventLogger()
    )

    monkeypatch.setattr(
        auth_route_module,
        "security_event_logger",
        recorder,
    )

    get_login_throttle.cache_clear()

    email = (
        "missing-login-"
        f"{uuid4().hex}"
        "@example.com"
    )

    try:
        response = (
            client.post(
                "/api/v1/auth/token",
                data={
                    "username": (
                        email
                    ),
                    "password": (
                        LOGIN_PASSWORD
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 401
        ), response.text

        failed_event = (
            require_event(
                recorder,
                "auth.login.failed",
            )
        )

        serialized_event = (
            event_text(
                failed_event
            )
        )

        assert (
            LOGIN_PASSWORD
            not in serialized_event
        )

        assert (
            failed_event.reason
            == "invalid_credentials"
        )

        assert (
            failed_event
            .account_identifier
            == email
        )

        # The HTTP response must not reflect the submitted
        # password either.

        assert (
            LOGIN_PASSWORD
            not in response.text
        )

        assert (
            response.json()
            == {
                "detail": (
                    "Incorrect email or password."
                ),
            }
        )

    finally:
        get_login_throttle.cache_clear()


# =========================================================
# PASSWORD RESET CONFIRMATION FAILURE
# =========================================================


def test_invalid_reset_confirmation_does_not_send_recovery_secrets_to_security_event_logger(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    Password-reset confirmation contains two secrets:

        reset bearer credential
        replacement password

    Neither may cross the structured logging boundary when
    the recovery credential is rejected.
    """

    recorder = (
        RecordingSecurityEventLogger()
    )

    monkeypatch.setattr(
        auth_route_module,
        "security_event_logger",
        recorder,
    )

    response = (
        client.post(
            (
                "/api/v1/auth/"
                "password-reset/confirm"
            ),
            json={
                "token": (
                    RESET_TOKEN
                ),
                "new_password": (
                    RESET_PASSWORD
                ),
            },
        )
    )

    assert (
        response.status_code
        == 400
    ), response.text

    failed_event = (
        require_event(
            recorder,
            "auth.password_reset.failed",
        )
    )

    serialized_event = (
        event_text(
            failed_event
        )
    )

    assert (
        RESET_TOKEN
        not in serialized_event
    )

    assert (
        RESET_PASSWORD
        not in serialized_event
    )

    assert (
        failed_event.reason
        == (
            "invalid_or_expired_reset_credential"
        )
    )

    # Neither recovery secret may be reflected through the
    # public HTTP response.

    assert (
        RESET_TOKEN
        not in response.text
    )

    assert (
        RESET_PASSWORD
        not in response.text
    )

    assert (
        response.json()
        == {
            "detail": (
                "The password reset credential "
                "is invalid or expired."
            ),
        }
    )


# =========================================================
# INVALID ACCESS TOKEN
# =========================================================


def test_invalid_access_token_does_not_send_bearer_credential_to_security_event_logger(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    Bearer access tokens are credentials.

    Failed access-token resolution may be logged generically,
    but the Authorization credential itself must never be
    handed to the structured event logger.
    """

    recorder = (
        RecordingSecurityEventLogger()
    )

    monkeypatch.setattr(
        dependency_module,
        "security_event_logger",
        recorder,
    )

    response = (
        client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": (
                    "Bearer "
                    + ACCESS_TOKEN
                ),
            },
        )
    )

    assert (
        response.status_code
        == 401
    ), response.text

    failed_event = (
        require_event(
            recorder,
            "auth.access_token.failed",
        )
    )

    serialized_event = (
        event_text(
            failed_event
        )
    )

    assert (
        ACCESS_TOKEN
        not in serialized_event
    )

    assert (
        failed_event.reason
        == "invalid_access_token"
    )

    assert (
        ACCESS_TOKEN
        not in response.text
    )

    assert (
        response.json()
        == {
            "detail": (
                "Could not validate credentials."
            ),
        }
    )


# =========================================================
# SECURITY-EVENT DETAILS CONTRACT
# =========================================================


def test_authentication_failure_events_use_metadata_not_credential_fields(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    Authentication failure telemetry should contain safe
    operational metadata rather than arbitrary credential
    details.
    """

    recorder = (
        RecordingSecurityEventLogger()
    )

    monkeypatch.setattr(
        auth_route_module,
        "security_event_logger",
        recorder,
    )

    get_login_throttle.cache_clear()

    try:
        response = (
            client.post(
                "/api/v1/auth/token",
                data={
                    "username": (
                        "event-shape-"
                        f"{uuid4().hex}"
                        "@example.com"
                    ),
                    "password": (
                        LOGIN_PASSWORD
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 401
        ), response.text

        failed_event = (
            require_event(
                recorder,
                "auth.login.failed",
            )
        )

        assert (
            failed_event.details
            is None
        )

        assert (
            failed_event.path
            == "/api/v1/auth/token"
        )

        assert (
            failed_event.method
            == "POST"
        )

        assert (
            LOGIN_PASSWORD
            not in event_text(
                failed_event
            )
        )

    finally:
        get_login_throttle.cache_clear()