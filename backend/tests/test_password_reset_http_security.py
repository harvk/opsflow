from __future__ import annotations

import html
import re
import secrets

from collections.abc import (
    Iterator,
)

from typing import (
    Any,
)

from uuid import (
    uuid4,
)

import pytest

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy.orm import (
    Session,
)

from app.api.dependencies import (
    get_password_reset_throttle,
    get_ses_client,
)

from app.domain.user import (
    User,
    UserRole,
)

from app.main import (
    app,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# TEST CONSTANTS
# =========================================================


OLD_PASSWORD = (
    "VerySecurePassword123!"
)

NEW_PASSWORD = (
    "EvenMoreSecurePassword456!"
)

ANOTHER_NEW_PASSWORD = (
    "AnotherSecurePassword789!"
)

RESET_REQUEST_PATH = (
    "/api/v1/auth/"
    "password-reset/request"
)

RESET_CONFIRM_PATH = (
    "/api/v1/auth/"
    "password-reset/confirm"
)


# =========================================================
# RECORDING SES CLIENT
# =========================================================


class RecordingSesClient:
    """
    Test double for the AWS SES v2 network client.

    Everything above the actual AWS network boundary remains
    production code:

        HTTP route
            ↓
        PasswordResetService
            ↓
        persistence
            ↓
        PasswordResetDeliveryCoordinator
            ↓
        PasswordResetLinkBuilder
            ↓
        SesPasswordResetDelivery
            ↓
        RecordingSesClient

    This lets us inspect the actual recovery links that
    OpsFlow attempted to send without contacting AWS.
    """

    def __init__(
        self,
    ) -> None:
        self.requests: list[
            dict[
                str,
                Any,
            ]
        ] = []

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        self.requests.append(
            kwargs
        )

        return {
            "MessageId": (
                "password-reset-http-security-test"
            ),
        }


# =========================================================
# SES STRING WALKER
# =========================================================


def iter_string_values(
    value: Any,
) -> Iterator[str]:
    """
    Recursively yield strings from an SES request.

    The security tests should not be tightly coupled to the
    exact internal nesting of the SES request body.
    """

    if isinstance(
        value,
        str,
    ):
        yield value

        return

    if isinstance(
        value,
        dict,
    ):
        for nested_value in (
            value.values()
        ):
            yield from (
                iter_string_values(
                    nested_value
                )
            )

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
            yield from (
                iter_string_values(
                    nested_value
                )
            )


# =========================================================
# RESET TOKEN EXTRACTION
# =========================================================


RESET_TOKEN_PATTERN = (
    re.compile(
        r"token=([A-Za-z0-9_-]+)"
    )
)


def extract_reset_token(
    ses_request: dict[
        str,
        Any,
    ],
) -> str:
    """
    Extract the bearer recovery credential from the actual
    outbound SES message.

    The test never reaches into PasswordResetService to
    obtain the raw token directly.
    """

    for raw_text in (
        iter_string_values(
            ses_request
        )
    ):
        candidate = (
            html.unescape(
                raw_text
            )
        )

        match = (
            RESET_TOKEN_PATTERN.search(
                candidate
            )
        )

        if match is not None:
            return match.group(
                1
            )

    raise AssertionError(
        "The recorded SES request did not contain "
        "a password-reset token."
    )


# =========================================================
# TEST USER FACTORY
# =========================================================


def create_test_user(
    db_session: Session,
) -> User:
    """
    Create a unique active user so this suite cannot collide
    with another test's account or account-level throttle
    history.
    """

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = (
        UserService(
            repository
        )
    )

    return (
        service.create_user(
            email=(
                "password-reset-http-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Password Reset HTTP "
                "Security User"
            ),
            password=(
                OLD_PASSWORD
            ),
            role=(
                UserRole.OPERATOR
            ),
        )
    )


# =========================================================
# HTTP HELPERS
# =========================================================


def request_password_reset(
    client: TestClient,
    *,
    email: str,
):
    """
    Submit one reset request with an isolated process-local
    throttle instance.

    Throttling already has its own regression coverage.

    These tests are specifically about password-recovery
    response semantics, so throttle history from one request
    must not interfere with another assertion.
    """

    get_password_reset_throttle.cache_clear()

    return client.post(
        RESET_REQUEST_PATH,
        json={
            "email": email,
        },
    )


def confirm_password_reset(
    client: TestClient,
    *,
    token: str,
    new_password: str,
):
    return client.post(
        RESET_CONFIRM_PATH,
        json={
            "token": token,
            "new_password": (
                new_password
            ),
        },
    )


# =========================================================
# SES FIXTURE
# =========================================================


@pytest.fixture
def recording_ses_client(
) -> Iterator[
    RecordingSesClient
]:
    """
    Replace only the external SES network client.

    The real SesPasswordResetDelivery remains active.
    """

    recording_client = (
        RecordingSesClient()
    )

    get_password_reset_throttle.cache_clear()

    app.dependency_overrides[
        get_ses_client
    ] = (
        lambda: recording_client
    )

    try:
        yield recording_client

    finally:
        app.dependency_overrides.pop(
            get_ses_client,
            None,
        )

        get_password_reset_throttle.cache_clear()


# =========================================================
# ACCOUNT ENUMERATION CONTRACT
# =========================================================


def test_known_and_unknown_accounts_receive_same_public_response(
    client: TestClient,
    db_session: Session,
    recording_ses_client: (
        RecordingSesClient
    ),
) -> None:
    """
    The public endpoint must not disclose whether an email
    belongs to an eligible account.

    A known active account will cause internal recovery work
    and email delivery.

    An unknown account will not.

    The caller must nevertheless receive the same:

        HTTP status
        response body

    for both cases.
    """

    user = create_test_user(
        db_session
    )

    known_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        known_response.status_code
        == 202
    ), known_response.text

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 1
    )

    unknown_email = (
        "missing-password-reset-"
        f"{uuid4().hex}"
        "@example.com"
    )

    unknown_response = (
        request_password_reset(
            client,
            email=(
                unknown_email
            ),
        )
    )

    assert (
        unknown_response.status_code
        == known_response.status_code
    )

    assert (
        unknown_response.json()
        == known_response.json()
    )

    # The unknown account must not produce another outbound
    # recovery message.

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 1
    )


# =========================================================
# GENERIC INVALID-CREDENTIAL CONTRACT
# =========================================================


def test_invalid_superseded_and_used_tokens_share_public_error_contract(
    client: TestClient,
    db_session: Session,
    recording_ses_client: (
        RecordingSesClient
    ),
) -> None:
    """
    The API must not explain why a reset credential failed.

    These states all represent unusable bearer credentials:

        completely unknown token
        superseded token
        already-used token

    All should collapse to the same public HTTP contract.
    """

    user = create_test_user(
        db_session
    )

    # -----------------------------------------------------
    # FIRST RESET CREDENTIAL
    # -----------------------------------------------------

    first_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        first_response.status_code
        == 202
    ), first_response.text

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 1
    )

    first_token = (
        extract_reset_token(
            recording_ses_client
            .requests[
                0
            ]
        )
    )

    # -----------------------------------------------------
    # SECOND RESET CREDENTIAL
    # -----------------------------------------------------
    #
    # Issuing this credential should invalidate the first.

    second_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        second_response.status_code
        == 202
    ), second_response.text

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 2
    )

    second_token = (
        extract_reset_token(
            recording_ses_client
            .requests[
                1
            ]
        )
    )

    assert (
        first_token
        != second_token
    )

    # -----------------------------------------------------
    # RANDOM UNKNOWN TOKEN
    # -----------------------------------------------------

    unknown_token = (
        secrets.token_urlsafe(
            48
        )
    )

    unknown_response = (
        confirm_password_reset(
            client,
            token=(
                unknown_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        unknown_response.status_code
        == 400
    ), unknown_response.text

    generic_invalid_body = (
        unknown_response.json()
    )

    # -----------------------------------------------------
    # SUPERSEDED TOKEN
    # -----------------------------------------------------

    superseded_response = (
        confirm_password_reset(
            client,
            token=(
                first_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        superseded_response.status_code
        == 400
    ), superseded_response.text

    assert (
        superseded_response.json()
        == generic_invalid_body
    )

    # -----------------------------------------------------
    # CURRENT TOKEN SUCCEEDS
    # -----------------------------------------------------

    valid_response = (
        confirm_password_reset(
            client,
            token=(
                second_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        valid_response.status_code
        == 204
    ), valid_response.text

    # -----------------------------------------------------
    # ALREADY-USED TOKEN
    # -----------------------------------------------------

    replay_response = (
        confirm_password_reset(
            client,
            token=(
                second_token
            ),
            new_password=(
                ANOTHER_NEW_PASSWORD
            ),
        )
    )

    assert (
        replay_response.status_code
        == 400
    ), replay_response.text

    assert (
        replay_response.json()
        == generic_invalid_body
    )


# =========================================================
# SCHEMA PASSWORD POLICY
# =========================================================


def test_schema_password_policy_failure_does_not_consume_reset_token(
    client: TestClient,
    db_session: Session,
    recording_ses_client: (
        RecordingSesClient
    ),
) -> None:
    """
    A password rejected by request-schema validation must not
    burn an otherwise valid reset credential.

    Schema-level violations such as insufficient length are
    represented by FastAPI/Pydantic as HTTP 422.

    The user should be able to correct the password and
    resubmit the same recovery credential.
    """

    user = create_test_user(
        db_session
    )

    request_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        request_response.status_code
        == 202
    ), request_response.text

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 1
    )

    reset_token = (
        extract_reset_token(
            recording_ses_client
            .requests[
                0
            ]
        )
    )

    # -----------------------------------------------------
    # PASSWORD TOO SHORT
    # -----------------------------------------------------

    rejected_response = (
        confirm_password_reset(
            client,
            token=(
                reset_token
            ),
            new_password=(
                "TooShort123!"
            ),
        )
    )

    assert (
        rejected_response.status_code
        == 422
    ), rejected_response.text

    # -----------------------------------------------------
    # SAME TOKEN REMAINS VALID
    # -----------------------------------------------------

    successful_response = (
        confirm_password_reset(
            client,
            token=(
                reset_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        successful_response.status_code
        == 204
    ), successful_response.text


# =========================================================
# CURRENT PASSWORD REUSE
# =========================================================


def test_current_password_reuse_does_not_consume_reset_token(
    client: TestClient,
    db_session: Session,
    recording_ses_client: (
        RecordingSesClient
    ),
) -> None:
    """
    Password recovery must require an actual credential
    change.

    Unlike a schema-validation problem, the existing password
    is correctly shaped and satisfies the length constraint.
    The rejection occurs inside PasswordResetService after
    comparison with the currently stored credential.

    The application therefore represents this domain-level
    rule violation as HTTP 400.

    Most importantly, rejecting password reuse must happen
    before the reset credential is consumed, allowing the
    user to correct the replacement password without
    requesting another recovery email.
    """

    user = create_test_user(
        db_session
    )

    request_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        request_response.status_code
        == 202
    ), request_response.text

    assert (
        len(
            recording_ses_client
            .requests
        )
        == 1
    )

    reset_token = (
        extract_reset_token(
            recording_ses_client
            .requests[
                0
            ]
        )
    )

    # -----------------------------------------------------
    # ATTEMPT TO REUSE CURRENT PASSWORD
    # -----------------------------------------------------

    reuse_response = (
        confirm_password_reset(
            client,
            token=(
                reset_token
            ),
            new_password=(
                OLD_PASSWORD
            ),
        )
    )

    assert (
        reuse_response.status_code
        == 400
    ), reuse_response.text

    assert (
        reuse_response.json()
        == {
            "detail": (
                "The new password must differ "
                "from the current password."
            ),
        }
    )

    # -----------------------------------------------------
    # SAME TOKEN MUST STILL BE USABLE
    # -----------------------------------------------------

    successful_response = (
        confirm_password_reset(
            client,
            token=(
                reset_token
            ),
            new_password=(
                NEW_PASSWORD
            ),
        )
    )

    assert (
        successful_response.status_code
        == 204
    ), successful_response.text