from __future__ import annotations

from uuid import (
    uuid4,
)

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy import text

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from collections.abc import (
    Iterator,
)

from app.core.password_reset_tokens import (
    generate_password_reset_token,
)

from app.core.security import (
    hash_password,
    verify_password,
)

from app.domain.user import (
    User,
    UserRole,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.password_reset_service import (
    PasswordResetService,
)

from app.services.user_service import (
    UserService,
)

import pytest

from app.api.dependencies import (
    get_password_reset_delivery,
    get_password_reset_link_builder,
)

from app.main import (
    app,
)

from app.core.password_reset_tokens import (
    digest_password_reset_token,
    generate_password_reset_token,
)

from app.infrastructure.aws.ses_password_reset_delivery import (
    SesPasswordResetDelivery,
)

from tests.fakes.ses_client import (
    FailingSesClient,
)

from tests.fakes.password_reset_delivery import (
    RecordingPasswordResetDelivery,
)

from urllib.parse import (
    parse_qs,
    urlsplit,
)


OLD_PASSWORD = (
    "VerySecurePassword123!"
)

NEW_PASSWORD = (
    "EvenMoreSecurePassword456!"
)

ANOTHER_NEW_PASSWORD = (
    "AnotherSecurePassword789!"
)

RESET_REQUEST_MESSAGE = (
    "If an eligible account exists, "
    "password reset instructions will be sent."
)

INVALID_RESET_MESSAGE = (
    "The password reset credential "
    "is invalid or expired."
)


# =========================================================
# HELPERS
# =========================================================


def build_password_reset_service(
    db_session: Session,
) -> PasswordResetService:
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    reset_repository = (
        SqlAlchemyPasswordResetTokenRepository(
            db_session
        )
    )

    auth_session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    return PasswordResetService(
        user_repository=(
            user_repository
        ),
        password_reset_repository=(
            reset_repository
        ),
        auth_session_repository=(
            auth_session_repository
        ),
    )


def create_reset_test_user(
    db_session: Session,
) -> User:
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
                f"password-reset-api-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Password Reset API User"
            ),
            password=(
                OLD_PASSWORD
            ),
            role=(
                UserRole.VIEWER
            ),
        )
    )

    db_session.flush()

    return user


def create_inactive_reset_test_user(
    db_session: Session,
) -> User:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = (
        repository.add(
            email=(
                f"inactive-reset-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Inactive Password Reset User"
            ),
            hashed_password=(
                hash_password(
                    OLD_PASSWORD
                )
            ),
            role=(
                UserRole.VIEWER
            ),
            is_active=False,
        )
    )

    db_session.flush()

    return user


def issue_reset_token(
    db_session: Session,
    *,
    email: str,
) -> str:
    """
    Issue a real reset credential through the service layer.

    This helper exists only inside the test suite.

    Production HTTP responses never expose this credential.
    """

    service = (
        build_password_reset_service(
            db_session
        )
    )

    issuance = (
        service.request_reset(
            email=email
        )
    )

    assert (
        issuance
        is not None
    )

    return issuance.raw_token


def assert_no_store_headers(
    response,
) -> None:
    assert (
        "no-store"
        in response.headers[
            "cache-control"
        ].lower()
    )

    assert (
        response.headers[
            "pragma"
        ].lower()
        == "no-cache"
    )


# =========================================================
# RESET REQUEST — ENUMERATION RESISTANCE
# =========================================================


def test_password_reset_request_for_existing_account_returns_202(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert response.json() == {
        "message": (
            RESET_REQUEST_MESSAGE
        )
    }

    assert_no_store_headers(
        response
    )


def test_password_reset_request_for_unknown_account_returns_same_response(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    existing_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    unknown_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    f"missing-"
                    f"{uuid4().hex}"
                    "@example.com"
                ),
            },
        )
    )

    assert (
        existing_response.status_code
        == 202
    )

    assert (
        unknown_response.status_code
        == 202
    )

    assert (
        existing_response.json()
        == unknown_response.json()
    )

    assert (
        existing_response.json()
        == {
            "message": (
                RESET_REQUEST_MESSAGE
            )
        }
    )


def test_password_reset_request_for_inactive_account_returns_same_response(
    client: TestClient,
    db_session: Session,
) -> None:
    inactive_user = (
        create_inactive_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                inactive_user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert response.json() == {
        "message": (
            RESET_REQUEST_MESSAGE
        )
    }

    assert_no_store_headers(
        response
    )


def test_password_reset_request_does_not_expose_reset_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    body = response.json()

    assert set(
        body.keys()
    ) == {
        "message",
    }

    serialized_body = (
        response.text.lower()
    )

    assert (
        "raw_token"
        not in serialized_body
    )

    assert (
        "reset_token"
        not in serialized_body
    )

    assert (
        "access_token"
        not in serialized_body
    )

    assert (
        "refresh_token"
        not in serialized_body
    )


def test_password_reset_request_does_not_require_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    # Deliberately no Authorization header.
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )


# =========================================================
# RESET CONFIRMATION — SUCCESS
# =========================================================


def test_password_reset_confirm_changes_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                raw_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    assert (
        response.content
        == b""
    )

    assert_no_store_headers(
        response
    )

    db_session.expire_all()

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    auth_record = (
        repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    assert verify_password(
        NEW_PASSWORD,
        auth_record.hashed_password,
    )

    assert not verify_password(
        OLD_PASSWORD,
        auth_record.hashed_password,
    )


def test_password_reset_confirm_does_not_auto_login_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    reset_response = (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": (
                    raw_token
                ),
                "new_password": (
                    NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        reset_response.status_code
        == 204
    )

    # Recovery alone must not create an authenticated
    # application session.
    me_response = (
        client.get(
            "/api/v1/auth/me"
        )
    )

    assert (
        me_response.status_code
        == 401
    )


def test_password_reset_confirm_does_not_return_tokens(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                raw_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    assert (
        response.content
        == b""
    )


# =========================================================
# RESET CONFIRMATION — INVALID CREDENTIALS
# =========================================================


def test_password_reset_confirm_rejects_unknown_token_generically(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                generate_password_reset_token()
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            INVALID_RESET_MESSAGE
        )
    }

    assert_no_store_headers(
        response
    )


def test_password_reset_confirm_rejects_reused_token_generically(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    first_response = (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": (
                    raw_token
                ),
                "new_password": (
                    NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        first_response.status_code
        == 204
    )

    second_response = (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": (
                    raw_token
                ),
                "new_password": (
                    ANOTHER_NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        second_response.status_code
        == 400
    )

    assert second_response.json() == {
        "detail": (
            INVALID_RESET_MESSAGE
        )
    }


# =========================================================
# PASSWORD VALIDATION AT HTTP BOUNDARY
# =========================================================


def test_password_reset_confirm_rejects_short_password_at_schema_boundary(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                generate_password_reset_token()
            ),
            "new_password": (
                "TooShort123!"
            ),
        },
    )

    # NewPassword is constrained by the Pydantic schema
    # before PasswordResetService executes.
    assert (
        response.status_code
        == 422
    )


def test_password_reset_confirm_rejects_current_password_reuse(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                raw_token
            ),
            "new_password": (
                OLD_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            "The new password must differ "
            "from the current password."
        )
    }


# =========================================================
# AUTHENTICATION COOKIE CLEANUP
# =========================================================


def test_successful_password_reset_clears_existing_auth_cookies(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    raw_token = (
        issue_reset_token(
            db_session,
            email=(
                user.email
            ),
        )
    )

    # Simulate credentials that may already exist in this
    # browser before account recovery.
    client.cookies.set(
        settings.refresh_cookie_name,
        "stale-refresh-token",
        domain=(
            "testserver.local"
        ),
        path=(
            settings
            .refresh_cookie_path
        ),
    )

    client.cookies.set(
        settings.csrf_cookie_name,
        "stale-csrf-token",
        domain=(
            "testserver.local"
        ),
        path="/",
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": (
                raw_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is None
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        is None
    )
    
def test_password_reset_request_is_throttled_by_account(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    for _ in range(
        settings
        .password_reset_account_max_requests
    ):
        response = (
            client.post(
                "/api/v1/auth/password-reset/request",
                json={
                    "email": (
                        user.email
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 202
        )

    blocked_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    assert (
        blocked_response.status_code
        == 429
    )

    assert blocked_response.json() == {
        "detail": (
            "Too many password reset "
            "requests. Please try again later."
        )
    }
    
def test_password_reset_throttle_returns_retry_after(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    for _ in range(
        settings
        .password_reset_account_max_requests
    ):
        response = (
            client.post(
                "/api/v1/auth/password-reset/request",
                json={
                    "email": (
                        user.email
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 202
        )

    blocked_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    assert (
        blocked_response.status_code
        == 429
    )

    retry_after = (
        blocked_response.headers.get(
            "retry-after"
        )
    )

    assert (
        retry_after
        is not None
    )

    assert (
        int(
            retry_after
        )
        >= 1
    )
    
def test_password_reset_throttle_response_is_not_cacheable(
    client: TestClient,
    db_session: Session,
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    for _ in range(
        settings
        .password_reset_account_max_requests
    ):
        (
            client.post(
                "/api/v1/auth/password-reset/request",
                json={
                    "email": (
                        user.email
                    ),
                },
            )
        )

    response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    assert (
        response.status_code
        == 429
    )

    assert (
        "no-store"
        in response.headers[
            "cache-control"
        ].lower()
    )

    assert (
        response.headers[
            "pragma"
        ].lower()
        == "no-cache"
    )
    
def test_password_reset_request_is_throttled_by_ip(
    client: TestClient,
) -> None:
    for index in range(
        settings
        .password_reset_ip_max_requests
    ):
        response = (
            client.post(
                "/api/v1/auth/password-reset/request",
                json={
                    "email": (
                        f"ip-throttle-"
                        f"{index}"
                        "@example.com"
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 202
        )

    blocked_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    "ip-throttle-blocked"
                    "@example.com"
                ),
            },
        )
    )

    assert (
        blocked_response.status_code
        == 429
    )
    
@pytest.fixture
def recording_password_reset_delivery(
) -> Iterator[
    RecordingPasswordResetDelivery
]:
    """
    Replace the application's delivery adapter with a
    recording test double.

    The real application route and coordinator still execute;
    only the infrastructure transport is replaced.
    """

    delivery = (
        RecordingPasswordResetDelivery()
    )

    app.dependency_overrides[
        get_password_reset_delivery
    ] = lambda: delivery

    get_password_reset_link_builder.cache_clear()

    try:
        yield delivery

    finally:
        app.dependency_overrides.pop(
            get_password_reset_delivery,
            None,
        )

        get_password_reset_link_builder.cache_clear()
    
def test_password_reset_request_delivers_for_existing_account(
    client: TestClient,
    db_session: Session,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert len(
        recording_password_reset_delivery
        .messages
    ) == 1

    message = (
        recording_password_reset_delivery
        .messages[0]
    )

    assert (
        message.recipient_email
        == user.email
    )
    
def test_password_reset_delivery_contains_reset_credential(
    client: TestClient,
    db_session: Session,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert len(
        recording_password_reset_delivery
        .messages
    ) == 1

    message = (
        recording_password_reset_delivery
        .messages[0]
    )

    parsed = urlsplit(
        message.reset_url
    )

    query = parse_qs(
        parsed.query
    )

    assert (
        "token"
        in query
    )

    assert len(
        query[
            "token"
        ]
    ) == 1

    raw_token = (
        query[
            "token"
        ][0]
    )

    assert (
        raw_token
    )

    # The HTTP response itself still exposes nothing.
    assert (
        raw_token
        not in response.text
    )
    
def test_unknown_account_does_not_generate_delivery(
    client: TestClient,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                f"missing-"
                f"{uuid4().hex}"
                "@example.com"
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert response.json() == {
        "message": (
            RESET_REQUEST_MESSAGE
        )
    }

    assert (
        recording_password_reset_delivery
        .messages
        == []
    )
    
def test_inactive_account_does_not_generate_delivery(
    client: TestClient,
    db_session: Session,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    user = (
        create_inactive_reset_test_user(
            db_session
        )
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={
            "email": (
                user.email
            ),
        },
    )

    assert (
        response.status_code
        == 202
    )

    assert response.json() == {
        "message": (
            RESET_REQUEST_MESSAGE
        )
    }

    assert (
        recording_password_reset_delivery
        .messages
        == []
    )
    
def test_delivered_reset_link_can_complete_password_reset(
    client: TestClient,
    db_session: Session,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    request_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    assert (
        request_response.status_code
        == 202
    )

    assert len(
        recording_password_reset_delivery
        .messages
    ) == 1

    reset_url = (
        recording_password_reset_delivery
        .messages[0]
        .reset_url
    )

    query = parse_qs(
        urlsplit(
            reset_url
        ).query
    )

    raw_token = (
        query[
            "token"
        ][0]
    )

    confirmation_response = (
        client.post(
            "/api/v1/auth/password-reset/confirm",
            json={
                "token": (
                    raw_token
                ),
                "new_password": (
                    NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        confirmation_response.status_code
        == 204
    )

    db_session.expire_all()

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    auth_record = (
        repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    assert verify_password(
        NEW_PASSWORD,
        auth_record.hashed_password,
    )

    assert not verify_password(
        OLD_PASSWORD,
        auth_record.hashed_password,
    )
    
def test_throttled_password_reset_request_does_not_deliver(
    client: TestClient,
    db_session: Session,
    recording_password_reset_delivery: (
        RecordingPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    max_requests = (
        settings
        .password_reset_account_max_requests
    )

    for _ in range(
        max_requests
    ):
        response = (
            client.post(
                "/api/v1/auth/password-reset/request",
                json={
                    "email": (
                        user.email
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 202
        )

    assert len(
        recording_password_reset_delivery
        .messages
    ) == max_requests

    blocked_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                ),
            },
        )
    )

    assert (
        blocked_response.status_code
        == 429
    )

    # The blocked request must not create one more reset
    # credential or one more delivery.
    assert len(
        recording_password_reset_delivery
        .messages
    ) == max_requests
    
@pytest.fixture
def failing_password_reset_delivery(
) -> Iterator[
    SesPasswordResetDelivery
]:
    delivery = (
        SesPasswordResetDelivery(
            client=(
                FailingSesClient()
            ),
            sender_email=(
                "no-reply@example.com"
            ),
        )
    )

    app.dependency_overrides[
        get_password_reset_delivery
    ] = lambda: delivery

    try:
        yield delivery

    finally:
        app.dependency_overrides.pop(
            get_password_reset_delivery,
            None,
        )
        
def test_password_reset_delivery_failure_is_enumeration_safe(
    client: TestClient,
    db_session: Session,
    failing_password_reset_delivery: (
        SesPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    existing_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                )
            },
        )
    )

    unknown_response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    f"missing-"
                    f"{uuid4().hex}"
                    "@example.com"
                )
            },
        )
    )

    assert (
        existing_response.status_code
        == 202
    )

    assert (
        unknown_response.status_code
        == 202
    )

    assert (
        existing_response.json()
        == unknown_response.json()
    )

    assert (
        existing_response.json()
        == {
            "message": (
                RESET_REQUEST_MESSAGE
            )
        }
    )

    assert_no_store_headers(
        existing_response
    )

    assert_no_store_headers(
        unknown_response
    )
    
def test_failed_delivery_rolls_back_new_reset_credential(
    client: TestClient,
    db_session: Session,
    failing_password_reset_delivery: (
        SesPasswordResetDelivery
    ),
) -> None:
    user = (
        create_reset_test_user(
            db_session
        )
    )

    service = (
        build_password_reset_service(
            db_session
        )
    )

    previous_issuance = (
        service.request_reset(
            email=(
                user.email
            )
        )
    )

    assert (
        previous_issuance
        is not None
    )

    previous_digest = (
        digest_password_reset_token(
            previous_issuance
            .raw_token
        )
    )

    # The test Session is joined to the outer pytest
    # transaction with savepoints. Commit this preparation
    # state so the request-level rollback only needs to undo
    # the failed request work.
    db_session.commit()

    count_before = (
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
                    user.id
                )
            },
        )
        .scalar_one()
    )

    response = (
        client.post(
            "/api/v1/auth/password-reset/request",
            json={
                "email": (
                    user.email
                )
            },
        )
    )

    assert (
        response.status_code
        == 202
    )

    db_session.expire_all()

    reset_repository = (
        SqlAlchemyPasswordResetTokenRepository(
            db_session
        )
    )

    previous_record = (
        reset_repository
        .get_by_digest_for_update(
            previous_digest
        )
    )

    assert (
        previous_record
        is not None
    )

    # The failed request temporarily invalidated the prior
    # token before attempting SES delivery. The database
    # rollback must restore that state.
    assert (
        previous_record.invalidated_at
        is None
    )

    count_after = (
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
                    user.id
                )
            },
        )
        .scalar_one()
    )

    # The newly generated but undelivered reset credential
    # must not survive the failed transaction.
    assert (
        count_after
        == count_before
    )