from __future__ import annotations

from fastapi.testclient import (
    TestClient,
)

from app.core.auth_error_codes import (
    AUTH_ERROR_CODE_HEADER,
    AuthErrorCode,
    auth_error_headers,
)

from app.core.config import (
    settings,
)


# =========================================================
# HEADER CONSTRUCTION
# =========================================================


def test_auth_error_headers_adds_stable_code(
) -> None:
    headers = (
        auth_error_headers(
            AuthErrorCode
            .LOGIN_CREDENTIALS_INVALID
        )
    )

    assert (
        headers[
            AUTH_ERROR_CODE_HEADER
        ]
        == (
            AuthErrorCode
            .LOGIN_CREDENTIALS_INVALID
            .value
        )
    )


def test_auth_error_headers_preserves_functional_headers(
) -> None:
    headers = (
        auth_error_headers(
            AuthErrorCode
            .PASSWORD_RESET_THROTTLED,
            additional_headers={
                "Retry-After": "60",
            },
        )
    )

    assert (
        headers[
            "Retry-After"
        ]
        == "60"
    )

    assert (
        headers[
            AUTH_ERROR_CODE_HEADER
        ]
        == (
            AuthErrorCode
            .PASSWORD_RESET_THROTTLED
            .value
        )
    )


def test_auth_error_code_cannot_be_overridden_by_caller(
) -> None:
    headers = (
        auth_error_headers(
            AuthErrorCode
            .LOGIN_CREDENTIALS_INVALID,
            additional_headers={
                AUTH_ERROR_CODE_HEADER: (
                    "UNTRUSTED_OVERRIDE"
                ),
            },
        )
    )

    assert (
        headers[
            AUTH_ERROR_CODE_HEADER
        ]
        == (
            AuthErrorCode
            .LOGIN_CREDENTIALS_INVALID
            .value
        )
    )


# =========================================================
# LOGIN CONTRACT
# =========================================================


def test_invalid_login_returns_typed_error_code(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "missing-auth-code@example.com"
            ),
            "password": (
                "WrongPassword123!"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.headers.get(
            AUTH_ERROR_CODE_HEADER
        )
        == (
            AuthErrorCode
            .LOGIN_CREDENTIALS_INVALID
            .value
        )
    )

    assert (
        response.headers.get(
            "WWW-Authenticate"
        )
        == "Bearer"
    )


# =========================================================
# ACCESS TOKEN CONTRACT
# =========================================================


def test_missing_access_token_returns_typed_error_code(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/auth/me"
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.headers.get(
            AUTH_ERROR_CODE_HEADER
        )
        == (
            AuthErrorCode
            .ACCESS_CREDENTIALS_INVALID
            .value
        )
    )

    assert (
        response.headers.get(
            "WWW-Authenticate"
        )
        == "Bearer"
    )


def test_invalid_access_token_returns_same_typed_error_code(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                "Bearer "
                "definitely-not-a-valid-token"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.headers.get(
            AUTH_ERROR_CODE_HEADER
        )
        == (
            AuthErrorCode
            .ACCESS_CREDENTIALS_INVALID
            .value
        )
    )


# =========================================================
# PASSWORD RESET CONTRACT
# =========================================================


def test_invalid_reset_credential_returns_typed_error_code(
    client: TestClient,
) -> None:
    response = client.post(
        (
            "/api/v1/auth/"
            "password-reset/confirm"
        ),
        json={
            "token": (
                "x" * 32
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

    assert (
        response.headers.get(
            AUTH_ERROR_CODE_HEADER
        )
        == (
            AuthErrorCode
            .PASSWORD_RESET_CREDENTIAL_INVALID
            .value
        )
    )


# =========================================================
# CORS EXPOSURE
# =========================================================


def test_auth_error_code_is_exposed_to_frontend_origin(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Origin": (
                settings
                .frontend_origin
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    exposed_headers = (
        response.headers.get(
            "Access-Control-Expose-Headers",
            "",
        )
        .lower()
    )

    assert (
        "x-auth-error-code"
        in exposed_headers
    )

    assert (
        "retry-after"
        in exposed_headers
    )