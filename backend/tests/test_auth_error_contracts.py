from __future__ import annotations

from fastapi.testclient import (
    TestClient,
)

from pytest import (
    MonkeyPatch,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.auth_response_messages import (
    LOGIN_CREDENTIALS_INVALID_MESSAGE,
    PASSWORD_CHANGE_REJECTED_MESSAGE,
    PASSWORD_RESET_CREDENTIAL_INVALID_MESSAGE,
    PASSWORD_RESET_PASSWORD_REJECTED_MESSAGE,
    REFRESH_CREDENTIALS_INVALID_MESSAGE,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    create_access_token,
    hash_password,
)

from app.domain.user import (
    UserRole,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.authentication_service import (
    AuthenticationService,
    PasswordChangeError,
)

from app.services.password_reset_service import (
    InvalidPasswordResetCredentialError,
    PasswordResetPasswordError,
)


TEST_PASSWORD = (
    "VerySecurePassword123!"
)

SCHEMA_VALID_FAKE_RESET_TOKEN = (
    "x" * 32
)


# =========================================================
# USER HELPERS
# =========================================================


def create_active_user(
    db_session: Session,
    *,
    email: str,
):
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    return repository.add(
        email=email,
        full_name=(
            "Authentication Contract User"
        ),
        hashed_password=(
            hash_password(
                TEST_PASSWORD
            )
        ),
        role=(
            UserRole.VIEWER
        ),
        is_active=True,
    )


def create_inactive_user(
    db_session: Session,
    *,
    email: str,
):
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    return repository.add(
        email=email,
        full_name=(
            "Inactive Authentication User"
        ),
        hashed_password=(
            hash_password(
                TEST_PASSWORD
            )
        ),
        role=(
            UserRole.VIEWER
        ),
        is_active=False,
    )


# =========================================================
# LOGIN ENUMERATION RESISTANCE
# =========================================================


def test_inactive_account_login_uses_same_public_failure(
    client: TestClient,
    db_session: Session,
) -> None:
    create_inactive_user(
        db_session,
        email=(
            "inactive-login@example.com"
        ),
    )

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "inactive-login@example.com"
            ),
            "password": (
                TEST_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            LOGIN_CREDENTIALS_INVALID_MESSAGE
        )
    }

    assert (
        response.headers.get(
            "WWW-Authenticate"
        )
        == "Bearer"
    )

    body = (
        response.text.lower()
    )

    assert (
        "inactive"
        not in body
    )


def test_unknown_account_login_uses_same_public_failure(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "does-not-exist@example.com"
            ),
            "password": (
                TEST_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            LOGIN_CREDENTIALS_INVALID_MESSAGE
        )
    }


# =========================================================
# REFRESH ERROR NORMALIZATION
# =========================================================


def test_invalid_refresh_token_does_not_expose_decoder_reason(
    client: TestClient,
) -> None:
    client.cookies.set(
        settings
        .refresh_cookie_name,
        "definitely-not-a-valid-jwt",
        path=(
            settings
            .refresh_cookie_path
        ),
    )

    try:
        response = client.post(
            "/api/v1/auth/refresh"
        )

        assert (
            response.status_code
            == 401
        )

        assert response.json() == {
            "detail": (
                REFRESH_CREDENTIALS_INVALID_MESSAGE
            )
        }

        body = (
            response.text.lower()
        )

        assert (
            "invalid refresh token"
            not in body
        )

        assert (
            "jwt"
            not in body
        )

    finally:
        client.cookies.delete(
            settings
            .refresh_cookie_name,
            path=(
                settings
                .refresh_cookie_path
            ),
        )


# =========================================================
# PASSWORD CHANGE EXCEPTION BOUNDARY
# =========================================================


def test_password_change_does_not_expose_service_exception(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    user = create_active_user(
        db_session,
        email=(
            "password-change-contract@example.com"
        ),
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    internal_message = (
        "INTERNAL_PASSWORD_CHANGE_SENTINEL"
    )

    def reject_password_change(
        self,
        user,
        *,
        reauth_token: str,
        new_password: str,
    ):
        raise PasswordChangeError(
            internal_message
        )

    monkeypatch.setattr(
        AuthenticationService,
        "change_password",
        reject_password_change,
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            ),
        },
        json={
            "reauth_token": (
                "test-reauthentication-proof"
            ),
            "new_password": (
                "AnotherSecurePassword456!"
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            PASSWORD_CHANGE_REJECTED_MESSAGE
        )
    }

    assert (
        internal_message
        not in response.text
    )


# =========================================================
# PASSWORD RESET CREDENTIAL BOUNDARY
# =========================================================


def test_invalid_reset_credential_uses_stable_public_message(
    client: TestClient,
) -> None:
    response = client.post(
        (
            "/api/v1/auth/"
            "password-reset/confirm"
        ),
        json={
            "token": (
                SCHEMA_VALID_FAKE_RESET_TOKEN
            ),
            "new_password": (
                "AnotherSecurePassword456!"
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            PASSWORD_RESET_CREDENTIAL_INVALID_MESSAGE
        )
    }


# =========================================================
# PASSWORD RESET PASSWORD ERROR BOUNDARY
# =========================================================


def test_password_reset_password_error_does_not_expose_service_message(
    client: TestClient,
    monkeypatch: MonkeyPatch,
) -> None:
    internal_message = (
        "INTERNAL_RESET_PASSWORD_SENTINEL"
    )

    from app.services.password_reset_service import (
        PasswordResetService,
    )

    def reject_password(
        self,
        *,
        raw_token: str,
        new_password: str,
    ):
        raise PasswordResetPasswordError(
            internal_message
        )

    monkeypatch.setattr(
        PasswordResetService,
        "confirm_reset",
        reject_password,
    )

    response = client.post(
        (
            "/api/v1/auth/"
            "password-reset/confirm"
        ),
        json={
            "token": (
                SCHEMA_VALID_FAKE_RESET_TOKEN
            ),
            "new_password": (
                "AnotherSecurePassword456!"
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            PASSWORD_RESET_PASSWORD_REJECTED_MESSAGE
        )
    }

    assert (
        internal_message
        not in response.text
    )