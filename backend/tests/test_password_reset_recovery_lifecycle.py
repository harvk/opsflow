from __future__ import annotations

import hashlib
import html
import re

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_login_throttle,
    get_password_reset_throttle,
    get_ses_client,
)
from app.core.config import settings
from app.domain.user import User, UserRole
from app.main import app
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import UserService


# =========================================================
# TEST CONSTANTS
# =========================================================


OLD_PASSWORD = "VerySecurePassword123!"
NEW_PASSWORD = "EvenMoreSecurePassword456!"


# =========================================================
# RECORDING SES CLIENT
# =========================================================


class RecordingSesClient:
    """
    SES v2 test double.

    Only the external AWS network client is replaced.

    The application still traverses the real:

        HTTP route
        PasswordResetService
        password-reset repository
        PasswordResetDeliveryCoordinator
        PasswordResetLinkBuilder
        SesPasswordResetDelivery

    before reaching this object.
    """

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.requests.append(kwargs)

        return {
            "MessageId": "password-recovery-lifecycle-test",
        }


# =========================================================
# GENERAL NESTED-VALUE WALKER
# =========================================================


def iter_string_values(
    value: Any,
) -> Iterator[str]:
    """
    Recursively yield strings from the nested SES request.

    This keeps the lifecycle test from depending on the
    precise nesting of the SES Text/Html message structure.
    """

    if isinstance(value, str):
        yield value
        return

    if isinstance(value, dict):
        for nested_value in value.values():
            yield from iter_string_values(nested_value)

        return

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        for nested_value in value:
            yield from iter_string_values(nested_value)


# =========================================================
# RECOVERY TOKEN EXTRACTION
# =========================================================


RESET_TOKEN_PATTERN = re.compile(
    r"token=([A-Za-z0-9_-]+)"
)


def extract_reset_token_from_ses_request(
    ses_request: dict[str, Any],
) -> str:
    """
    Recover the bearer credential from the actual outbound
    recovery message.

    The test deliberately does not obtain the raw credential
    directly from PasswordResetService.
    """

    for raw_text in iter_string_values(
        ses_request
    ):
        candidate = html.unescape(
            raw_text
        )

        if (
            settings.password_reset_url
            not in candidate
        ):
            continue

        match = RESET_TOKEN_PATTERN.search(
            candidate
        )

        if match is not None:
            return match.group(1)

    raise AssertionError(
        "The recorded SES message did not contain "
        "a password-reset URL with a token."
    )


# =========================================================
# COOKIE HELPERS
# =========================================================


def require_cookie(
    client: TestClient,
    cookie_name: str,
) -> str:
    """
    Return an authentication cookie that must exist.
    """

    cookie_value = client.cookies.get(
        cookie_name
    )

    assert cookie_value is not None, (
        f"Expected cookie {cookie_name!r} "
        "to be present."
    )

    assert len(cookie_value) > 0

    return cookie_value


def build_cookie_header(
    *,
    refresh_token: str,
    csrf_token: str,
) -> str:
    """
    Reconstruct the exact pre-reset browser credential set.

    Password-reset confirmation should clear the TestClient
    cookie jar, but we still need to prove that credentials
    captured before the reset cannot be replayed afterward.
    """

    return (
        f"{settings.refresh_cookie_name}"
        f"={refresh_token}; "
        f"{settings.csrf_cookie_name}"
        f"={csrf_token}"
    )


# =========================================================
# USER FACTORY
# =========================================================


def create_recovery_user(
    db_session: Session,
) -> User:
    """
    Create a unique account for the lifecycle test.
    """

    repository = SqlAlchemyUserRepository(
        db_session
    )

    user_service = UserService(
        repository
    )

    user = user_service.create_user(
        email=(
            "password-recovery-lifecycle-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Password Recovery Lifecycle User"
        ),
        password=OLD_PASSWORD,
        role=UserRole.OPERATOR,
    )

    db_session.flush()

    return user


# =========================================================
# FULL PASSWORD-RECOVERY LIFECYCLE
# =========================================================


def test_password_recovery_full_http_lifecycle(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Exercise the complete backend password-recovery path.

    Verified boundaries:

        old password
            ↓
        login
            ↓
        persistent refresh session
            ↓
        password-reset request
            ↓
        persistent reset-token digest
            ↓
        recovery coordinator
            ↓
        reset-link builder
            ↓
        real SES delivery adapter
            ↓
        recording SES client
            ↓
        reset credential extracted from email
            ↓
        password-reset confirmation
            ↓
        credential consumption
            ↓
        old-session revocation
            ↓
        old password rejected
            ↓
        new password accepted
            ↓
        new refresh lifecycle
            ↓
        logout
    """

    # =====================================================
    # ISOLATE PROCESS-LOCAL THROTTLE STATE
    # =====================================================

    get_login_throttle.cache_clear()
    get_password_reset_throttle.cache_clear()

    recording_ses_client = (
        RecordingSesClient()
    )

    app.dependency_overrides[
        get_ses_client
    ] = lambda: recording_ses_client

    try:
        # =================================================
        # STEP 1
        # CREATE ACCOUNT
        # =================================================

        user = create_recovery_user(
            db_session
        )

        # =================================================
        # STEP 2
        # INITIAL LOGIN
        # =================================================

        login_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": user.email,
                "password": OLD_PASSWORD,
            },
        )

        assert (
            login_response.status_code
            == 200
        ), login_response.text

        login_body = (
            login_response.json()
        )

        assert (
            isinstance(
                login_body.get(
                    "access_token"
                ),
                str,
            )
        )

        assert (
            login_body["access_token"]
        )

        # Login must have established both halves of the
        # persistent cookie-authentication boundary.

        initial_refresh_token = (
            require_cookie(
                client,
                settings.refresh_cookie_name,
            )
        )

        initial_csrf_token = (
            require_cookie(
                client,
                settings.csrf_cookie_name,
            )
        )

        assert initial_refresh_token
        assert initial_csrf_token

        # =================================================
        # STEP 3
        # PROVE THE INITIAL SESSION IS LIVE
        # =================================================

        pre_reset_refresh_response = (
            client.post(
                "/api/v1/auth/refresh",
                headers={
                    settings.csrf_header_name: (
                        initial_csrf_token
                    ),
                },
            )
        )

        assert (
            pre_reset_refresh_response
            .status_code
            == 200
        ), (
            pre_reset_refresh_response
            .text
        )

        pre_reset_refresh_body = (
            pre_reset_refresh_response
            .json()
        )

        assert (
            pre_reset_refresh_body.get(
                "access_token"
            )
        )

        # Refresh rotation replaces the refresh credential.
        #
        # Save the CURRENT credential. This is the credential
        # that must become unusable when password recovery
        # revokes all persistent sessions.

        stale_refresh_token = (
            require_cookie(
                client,
                settings.refresh_cookie_name,
            )
        )

        stale_csrf_token = (
            require_cookie(
                client,
                settings.csrf_cookie_name,
            )
        )

        # =================================================
        # STEP 4
        # REQUEST PASSWORD RECOVERY
        # =================================================

        reset_request_response = (
            client.post(
                (
                    "/api/v1/auth/"
                    "password-reset/request"
                ),
                json={
                    "email": user.email,
                },
            )
        )

        assert (
            reset_request_response
            .status_code
            == 202
        ), (
            reset_request_response
            .text
        )

        reset_request_body = (
            reset_request_response
            .json()
        )

        assert (
            isinstance(
                reset_request_body.get(
                    "message"
                ),
                str,
            )
        )

        assert (
            reset_request_body[
                "message"
            ]
        )

        # =================================================
        # STEP 5
        # VERIFY THE REAL SES PATH WAS REACHED
        # =================================================

        assert (
            len(
                recording_ses_client
                .requests
            )
            == 1
        )

        ses_request = (
            recording_ses_client
            .requests[0]
        )

        ses_strings = list(
            iter_string_values(
                ses_request
            )
        )

        # The intended account must be represented in the
        # actual outbound SES request.

        assert (
            user.email
            in ses_strings
        )

        # =================================================
        # STEP 6
        # RECOVER THE LINK CREDENTIAL FROM THE EMAIL
        # =================================================

        reset_token = (
            extract_reset_token_from_ses_request(
                ses_request
            )
        )

        assert reset_token

        # The bearer reset credential must never be exposed
        # in the public reset-request response.

        assert (
            reset_token
            not in reset_request_response.text
        )

        # =================================================
        # STEP 7
        # VERIFY ONLY THE DIGEST WAS PERSISTED
        # =================================================

        expected_digest = (
            hashlib.sha256(
                reset_token.encode(
                    "utf-8"
                )
            )
            .hexdigest()
        )

        reset_row = (
            db_session.execute(
                text(
                    """
                    SELECT
                        token_digest,
                        used_at,
                        invalidated_at
                    FROM password_reset_tokens
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "user_id": user.id,
                },
            )
            .mappings()
            .one()
        )

        assert (
            reset_row[
                "token_digest"
            ]
            == expected_digest
        )

        assert (
            reset_row[
                "token_digest"
            ]
            != reset_token
        )

        assert (
            reset_row["used_at"]
            is None
        )

        assert (
            reset_row[
                "invalidated_at"
            ]
            is None
        )

        # =================================================
        # STEP 8
        # CONFIRM PASSWORD RESET
        # =================================================

        reset_confirmation_response = (
            client.post(
                (
                    "/api/v1/auth/"
                    "password-reset/confirm"
                ),
                json={
                    "token": reset_token,
                    "new_password": (
                        NEW_PASSWORD
                    ),
                },
            )
        )

        assert (
            reset_confirmation_response
            .status_code
            == 204
        ), (
            reset_confirmation_response
            .text
        )

        # =================================================
        # STEP 9
        # VERIFY RESET CREDENTIAL WAS CONSUMED
        # =================================================

        consumed_row = (
            db_session.execute(
                text(
                    """
                    SELECT
                        token_digest,
                        used_at,
                        invalidated_at
                    FROM password_reset_tokens
                    WHERE user_id = :user_id
                      AND token_digest = :token_digest
                    """
                ),
                {
                    "user_id": user.id,
                    "token_digest": (
                        expected_digest
                    ),
                },
            )
            .mappings()
            .one()
        )

        assert (
            consumed_row[
                "used_at"
            ]
            is not None
        )

        # =================================================
        # STEP 10
        # VERIFY TOKEN REPLAY FAILS
        # =================================================

        replay_response = (
            client.post(
                (
                    "/api/v1/auth/"
                    "password-reset/confirm"
                ),
                json={
                    "token": reset_token,
                    "new_password": (
                        "AnotherSecurePassword789!"
                    ),
                },
            )
        )

        assert (
            replay_response.status_code
            == 400
        ), replay_response.text

        # =================================================
        # STEP 11
        # VERIFY THE OLD PERSISTENT SESSION WAS REVOKED
        # =================================================
        #
        # Password reset clears this browser's cookies.
        #
        # To prove server-side revocation rather than merely
        # client-side deletion, deliberately reconstruct the
        # cookie set that was valid immediately before the
        # reset and attempt to use it again.

        stale_session_response = (
            client.post(
                "/api/v1/auth/refresh",
                headers={
                    "Cookie": (
                        build_cookie_header(
                            refresh_token=(
                                stale_refresh_token
                            ),
                            csrf_token=(
                                stale_csrf_token
                            ),
                        )
                    ),
                    settings.csrf_header_name: (
                        stale_csrf_token
                    ),
                },
            )
        )

        assert (
            stale_session_response
            .status_code
            == 401
        ), stale_session_response.text

        # =================================================
        # STEP 12
        # VERIFY OLD PASSWORD NO LONGER WORKS
        # =================================================

        old_password_response = (
            client.post(
                "/api/v1/auth/token",
                data={
                    "username": user.email,
                    "password": OLD_PASSWORD,
                },
            )
        )

        assert (
            old_password_response
            .status_code
            == 401
        ), old_password_response.text

        # =================================================
        # STEP 13
        # VERIFY NEW PASSWORD WORKS
        # =================================================

        new_password_response = (
            client.post(
                "/api/v1/auth/token",
                data={
                    "username": user.email,
                    "password": NEW_PASSWORD,
                },
            )
        )

        assert (
            new_password_response
            .status_code
            == 200
        ), new_password_response.text

        new_login_body = (
            new_password_response
            .json()
        )

        assert (
            new_login_body.get(
                "access_token"
            )
        )

        # A completely fresh persistent session should now
        # exist.

        fresh_refresh_token = (
            require_cookie(
                client,
                settings.refresh_cookie_name,
            )
        )

        fresh_csrf_token = (
            require_cookie(
                client,
                settings.csrf_cookie_name,
            )
        )

        assert (
            fresh_refresh_token
            != stale_refresh_token
        )

        # =================================================
        # STEP 14
        # VERIFY FRESH REFRESH LIFECYCLE
        # =================================================

        fresh_refresh_response = (
            client.post(
                "/api/v1/auth/refresh",
                headers={
                    settings.csrf_header_name: (
                        fresh_csrf_token
                    ),
                },
            )
        )

        assert (
            fresh_refresh_response
            .status_code
            == 200
        ), fresh_refresh_response.text

        assert (
            fresh_refresh_response
            .json()
            .get(
                "access_token"
            )
        )

        # =================================================
        # STEP 15
        # LOG OUT OF THE FRESH SESSION
        # =================================================

        logout_csrf_token = (
            require_cookie(
                client,
                settings.csrf_cookie_name,
            )
        )

        logout_response = (
            client.post(
                "/api/v1/auth/logout",
                headers={
                    settings.csrf_header_name: (
                        logout_csrf_token
                    ),
                },
            )
        )

        assert (
            logout_response.status_code
            == 204
        ), logout_response.text

        # =================================================
        # STEP 16
        # REFRESH AFTER LOGOUT MUST FAIL
        # =================================================

        post_logout_refresh_response = (
            client.post(
                "/api/v1/auth/refresh",
                headers={
                    settings.csrf_header_name: (
                        logout_csrf_token
                    ),
                },
            )
        )

        assert (
            post_logout_refresh_response
            .status_code
            == 401
        ), (
            post_logout_refresh_response
            .text
        )

    finally:
        # Remove only the override introduced by this test.
        #
        # The shared client fixture still owns the database
        # override and will clear its dependency state during
        # fixture teardown.

        app.dependency_overrides.pop(
            get_ses_client,
            None,
        )

        # Do not allow limiter history from this lifecycle
        # test to influence later tests in the same process.

        get_login_throttle.cache_clear()

        get_password_reset_throttle.cache_clear()