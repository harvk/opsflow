from __future__ import annotations

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

from botocore.exceptions import (
    ClientError,
)

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy import (
    text,
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
# HTTP CONTRACT
# =========================================================


PASSWORD_RESET_REQUEST_PATH = (
    "/api/v1/auth/"
    "password-reset/request"
)


# =========================================================
# TEST PASSWORD
# =========================================================


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# FAILING SES CLIENT
# =========================================================


class FailingSesClient:
    """
    SES v2 test double that behaves like a provider-side
    message rejection.

    This replaces only the external AWS client.

    The real application must still execute:

        password-reset route
            ↓
        PasswordResetService
            ↓
        PasswordResetDeliveryCoordinator
            ↓
        PasswordResetLinkBuilder
            ↓
        SesPasswordResetDelivery
            ↓
        FailingSesClient

    The failure therefore occurs at the same architectural
    boundary as a real SES rejection.
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

        raise ClientError(
            {
                "Error": {
                    "Code": (
                        "MessageRejected"
                    ),
                    "Message": (
                        "SES rejected the "
                        "password-reset message."
                    ),
                },
            },
            "SendEmail",
        )


# =========================================================
# TEST USER FACTORY
# =========================================================


def create_delivery_failure_user(
    db_session: Session,
) -> User:
    """
    Create a unique active account for each delivery-failure
    test.

    A unique email also prevents account-level throttle state
    from one test influencing another.
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

    user = (
        service.create_user(
            email=(
                "password-reset-delivery-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Password Reset Delivery "
                "Failure User"
            ),
            password=(
                TEST_PASSWORD
            ),
            role=(
                UserRole.OPERATOR
            ),
        )
    )

    db_session.flush()

    return user


# =========================================================
# REQUEST HELPER
# =========================================================


def request_password_reset(
    client: TestClient,
    *,
    email: str,
):
    """
    Execute one password-reset request.

    Password-reset throttling has dedicated coverage
    elsewhere.

    Resetting the process-local limiter keeps this suite
    focused exclusively on provider-failure behavior.
    """

    get_password_reset_throttle.cache_clear()

    return (
        client.post(
            PASSWORD_RESET_REQUEST_PATH,
            json={
                "email": email,
            },
        )
    )


# =========================================================
# FAILING SES FIXTURE
# =========================================================


@pytest.fixture
def failing_ses_client(
) -> Iterator[
    FailingSesClient
]:
    """
    Replace only the network-facing SES client.

    The real SesPasswordResetDelivery remains in the
    dependency graph.
    """

    failing_client = (
        FailingSesClient()
    )

    get_password_reset_throttle.cache_clear()

    app.dependency_overrides[
        get_ses_client
    ] = (
        lambda: failing_client
    )

    try:
        yield failing_client

    finally:
        app.dependency_overrides.pop(
            get_ses_client,
            None,
        )

        get_password_reset_throttle.cache_clear()


# =========================================================
# DATABASE HELPERS
# =========================================================


def get_active_reset_token_count(
    db_session: Session,
    *,
    user_id,
) -> int:
    """
    Count currently usable-looking reset-token rows.

    A delivery failure must not leave behind an active bearer
    credential that the legitimate user never received.
    """

    result = (
        db_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM password_reset_tokens
                WHERE user_id = :user_id
                  AND used_at IS NULL
                  AND invalidated_at IS NULL
                  AND expires_at > NOW()
                """
            ),
            {
                "user_id": (
                    user_id
                ),
            },
        )
        .scalar_one()
    )

    return int(
        result
    )


def get_total_reset_token_count(
    db_session: Session,
    *,
    user_id,
) -> int:
    """
    Count all reset-token rows for the supplied account.

    This is useful for distinguishing:

        no credential created

    from:

        credential created then safely invalidated
    """

    result = (
        db_session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM password_reset_tokens
                WHERE user_id = :user_id
                """
            ),
            {
                "user_id": (
                    user_id
                ),
            },
        )
        .scalar_one()
    )

    return int(
        result
    )


# =========================================================
# ACCOUNT ENUMERATION DURING PROVIDER FAILURE
# =========================================================


def test_ses_failure_does_not_create_account_enumeration_signal(
    client: TestClient,
    db_session: Session,
    failing_ses_client: (
        FailingSesClient
    ),
) -> None:
    """
    A provider outage must not disclose that one submitted
    email belongs to a real account.

    The important comparison is:

        real account + SES failure

    versus:

        nonexistent account

    The public caller should receive the same:

        status code
        response body

    in both cases.

    Otherwise an attacker could deliberately observe a mail
    provider failure and use the difference as an account
    enumeration oracle.
    """

    user = (
        create_delivery_failure_user(
            db_session
        )
    )

    # -----------------------------------------------------
    # KNOWN ACCOUNT
    # -----------------------------------------------------

    known_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    # A known account causes the application to attempt
    # delivery.

    assert (
        len(
            failing_ses_client
            .requests
        )
        == 1
    )

    # -----------------------------------------------------
    # UNKNOWN ACCOUNT
    # -----------------------------------------------------

    unknown_email = (
        "missing-delivery-failure-"
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

    # An unknown account has nothing to deliver, so the SES
    # client should still have been called exactly once.

    assert (
        len(
            failing_ses_client
            .requests
        )
        == 1
    )

    # -----------------------------------------------------
    # PUBLIC CONTRACT
    # -----------------------------------------------------

    assert (
        known_response.status_code
        == unknown_response.status_code
    )

    assert (
        known_response.json()
        == unknown_response.json()
    )

    # The ordinary privacy-preserving password-reset request
    # contract should remain intact even while email delivery
    # is unavailable.

    assert (
        known_response.status_code
        == 202
    )


# =========================================================
# FAILED DELIVERY CREDENTIAL STATE
# =========================================================


def test_ses_failure_leaves_no_active_reset_credential(
    client: TestClient,
    db_session: Session,
    failing_ses_client: (
        FailingSesClient
    ),
) -> None:
    """
    If outbound delivery fails, the user never receives the
    newly generated bearer credential.

    That credential therefore must not remain active in
    persistence.

    Acceptable implementations include:

        create token
        attempt delivery
        delivery fails
        invalidate token

    or an architecture that prevents the credential from
    becoming active until delivery succeeds.

    What is NOT acceptable is:

        create active token
        delivery fails
        active token remains usable
    """

    user = (
        create_delivery_failure_user(
            db_session
        )
    )

    response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        len(
            failing_ses_client
            .requests
        )
        == 1
    )

    # The public endpoint must preserve its generic accepted
    # response rather than advertising the SES failure.

    assert (
        response.status_code
        == 202
    )

    # -----------------------------------------------------
    # SECURITY PROPERTY
    # -----------------------------------------------------

    active_count = (
        get_active_reset_token_count(
            db_session,
            user_id=(
                user.id
            ),
        )
    )

    assert (
        active_count
        == 0
    ), (
        "SES delivery failed, but an active password-reset "
        "credential remained in persistence."
    )


# =========================================================
# RECOVERY AFTER PROVIDER RESTORATION
# =========================================================


class RecordingSesClient:
    """
    Successful SES test double used after the simulated
    provider outage.

    This proves that a prior delivery failure does not leave
    the account's reset state permanently wedged.
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
                "delivery-recovery-test-message"
            ),
        }


def test_password_reset_request_recovers_after_ses_is_restored(
    client: TestClient,
    db_session: Session,
    failing_ses_client: (
        FailingSesClient
    ),
) -> None:
    """
    A temporary provider failure must not permanently poison
    password recovery for the account.

    Sequence:

        request #1
            ↓
        SES fails
            ↓
        no active credential remains

        SES restored

        request #2
            ↓
        delivery succeeds
            ↓
        exactly one active credential exists
    """

    user = (
        create_delivery_failure_user(
            db_session
        )
    )

    # -----------------------------------------------------
    # FIRST REQUEST — PROVIDER FAILURE
    # -----------------------------------------------------

    failed_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        failed_response.status_code
        == 202
    )

    assert (
        len(
            failing_ses_client
            .requests
        )
        == 1
    )

    assert (
        get_active_reset_token_count(
            db_session,
            user_id=(
                user.id
            ),
        )
        == 0
    )

    # A token row may have been created and subsequently
    # invalidated. That is fine. We record the count only so
    # the second half can reason about the resulting state.

    rows_after_failure = (
        get_total_reset_token_count(
            db_session,
            user_id=(
                user.id
            ),
        )
    )

    # -----------------------------------------------------
    # RESTORE DELIVERY
    # -----------------------------------------------------

    recording_client = (
        RecordingSesClient()
    )

    app.dependency_overrides[
        get_ses_client
    ] = (
        lambda: recording_client
    )

    # -----------------------------------------------------
    # SECOND REQUEST — PROVIDER HEALTHY
    # -----------------------------------------------------

    successful_response = (
        request_password_reset(
            client,
            email=(
                user.email
            ),
        )
    )

    assert (
        successful_response.status_code
        == 202
    )

    assert (
        len(
            recording_client
            .requests
        )
        == 1
    )

    # Exactly one newly delivered credential should now be
    # active.

    assert (
        get_active_reset_token_count(
            db_session,
            user_id=(
                user.id
            ),
        )
        == 1
    )

    rows_after_success = (
        get_total_reset_token_count(
            db_session,
            user_id=(
                user.id
            ),
        )
    )

    assert (
        rows_after_success
        >= rows_after_failure
    )


# =========================================================
# UNKNOWN ACCOUNT PROVIDER INDEPENDENCE
# =========================================================


def test_unknown_account_does_not_touch_ses_during_outage(
    client: TestClient,
    failing_ses_client: (
        FailingSesClient
    ),
) -> None:
    """
    Unknown accounts must not trigger email delivery.

    This protects both provider cost and the architecture's
    account-privacy boundary.

    The HTTP response still remains the same generic accepted
    contract used for eligible accounts.
    """

    unknown_email = (
        "definitely-missing-"
        f"{uuid4().hex}"
        "@example.com"
    )

    response = (
        request_password_reset(
            client,
            email=(
                unknown_email
            ),
        )
    )

    assert (
        response.status_code
        == 202
    )

    assert (
        len(
            failing_ses_client
            .requests
        )
        == 0
    )

    body = (
        response.json()
    )

    assert (
        isinstance(
            body.get(
                "message"
            ),
            str,
        )
    )

    assert (
        body[
            "message"
        ]
    )