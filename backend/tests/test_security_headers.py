from httpx import (
    Response,
)

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from app.domain.user import (
    UserRole,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# ROUTE CONSTANTS
# =========================================================


HEALTH_PATH = (
    f"{settings.api_v1_prefix}/health"
)

TOKEN_PATH = (
    f"{settings.api_v1_prefix}/auth/token"
)

REFRESH_PATH = (
    f"{settings.api_v1_prefix}/auth/refresh"
)

LOGOUT_PATH = (
    f"{settings.api_v1_prefix}/auth/logout"
)

ME_PATH = (
    f"{settings.api_v1_prefix}/auth/me"
)

MISSING_PATH = (
    f"{settings.api_v1_prefix}/"
    "this-route-does-not-exist"
)


# =========================================================
# AUTHENTICATION TEST CONSTANTS
# =========================================================


TEST_EMAIL = (
    "security-headers@example.com"
)

TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# SECURITY HEADER EXPECTATIONS
# =========================================================


EXPECTED_SECURITY_HEADERS = {
    "x-content-type-options": (
        "nosniff"
    ),
    "x-frame-options": (
        "DENY"
    ),
    "referrer-policy": (
        "strict-origin-when-cross-origin"
    ),
    "permissions-policy": (
        "camera=(), "
        "microphone=(), "
        "geolocation=()"
    ),
    "x-permitted-cross-domain-policies": (
        "none"
    ),
}


EXPECTED_HSTS = (
    "max-age=31536000; "
    "includeSubDomains"
)


# =========================================================
# SHARED TEST HELPERS
# =========================================================


def assert_security_headers(
    response: Response,
) -> None:
    """
    Assert that the complete baseline OpsFlow HTTP security
    policy is present on a response.

    Header lookup through httpx.Response.headers is
    case-insensitive.
    """

    for (
        header_name,
        expected_value,
    ) in (
        EXPECTED_SECURITY_HEADERS.items()
    ):
        assert (
            response.headers.get(
                header_name
            )
            == expected_value
        )


def create_test_user(
    db_session: Session,
) -> None:
    """
    Create the user needed to establish a real refresh/CSRF
    browser authentication state.
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

    service.create_user(
        email=TEST_EMAIL,
        full_name=(
            "Security Header User"
        ),
        password=TEST_PASSWORD,
        role=UserRole.ADMIN,
    )


def login_test_user(
    client: TestClient,
    db_session: Session,
) -> Response:
    """
    Authenticate through the real OpsFlow login route.

    The response establishes:

        access JWT response
        HttpOnly refresh cookie
        readable CSRF cookie
    """

    create_test_user(
        db_session
    )

    response = client.post(
        TOKEN_PATH,
        data={
            "username": (
                TEST_EMAIL
            ),
            "password": (
                TEST_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 200
    ), response.text

    return response


# =========================================================
# SUCCESS RESPONSES
# =========================================================


def test_security_headers_are_added_to_success_response(
    client: TestClient,
) -> None:
    """
    Baseline case: a normal successful API response receives
    every configured security header.
    """

    response = client.get(
        HEALTH_PATH
    )

    assert (
        response.status_code
        == 200
    )

    assert_security_headers(
        response
    )


def test_security_headers_are_added_to_204_response(
    client: TestClient,
) -> None:
    """
    Security headers must also be added when the response has
    no body.

    Logout without a refresh credential is intentionally
    idempotent and returns HTTP 204.
    """

    response = client.post(
        LOGOUT_PATH
    )

    assert (
        response.status_code
        == 204
    )

    assert_security_headers(
        response
    )


# =========================================================
# FRAMEWORK-GENERATED RESPONSES
# =========================================================


def test_security_headers_are_added_to_404_response(
    client: TestClient,
) -> None:
    """
    Security policy must not depend on successfully matching
    an OpsFlow API route.
    """

    response = client.get(
        MISSING_PATH
    )

    assert (
        response.status_code
        == 404
    )

    assert_security_headers(
        response
    )


# =========================================================
# AUTHENTICATION FAILURES
# =========================================================


def test_security_headers_are_added_to_401_response(
    client: TestClient,
) -> None:
    """
    Authentication failures still cross the same response
    security boundary.
    """

    response = client.get(
        ME_PATH
    )

    assert (
        response.status_code
        == 401
    )

    assert_security_headers(
        response
    )


def test_security_headers_are_added_to_missing_refresh_401(
    client: TestClient,
) -> None:
    """
    Route-generated refresh failures must receive the same
    baseline policy.
    """

    response = client.post(
        REFRESH_PATH
    )

    assert (
        response.status_code
        == 401
    )

    assert_security_headers(
        response
    )


# =========================================================
# CSRF FAILURES
# =========================================================


def test_security_headers_are_added_to_csrf_403(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Establish real refresh + CSRF cookies, then omit the
    required CSRF header.

    The authentication route should return HTTP 403.

    Security headers must still be applied.
    """

    login_test_user(
        client,
        db_session,
    )

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is not None
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        is not None
    )

    response = client.post(
        REFRESH_PATH
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    assert_security_headers(
        response
    )


# =========================================================
# BROWSER TRUST FAILURES
# =========================================================


def test_security_headers_are_added_to_untrusted_origin_403(
    client: TestClient,
) -> None:
    """
    BrowserTrustBoundaryMiddleware generates this response
    directly.

    This test is therefore especially important.

    It proves SecurityHeadersMiddleware is outside the
    browser-trust layer rather than being bypassed by the
    middleware's direct JSONResponse.
    """

    response = client.post(
        TOKEN_PATH,
        data={
            "username": (
                "missing@example.com"
            ),
            "password": (
                "WrongPassword123!"
            ),
        },
        headers={
            "Origin": (
                "https://evil.example"
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "Request origin is not trusted."
        )
    }

    assert_security_headers(
        response
    )


def test_security_headers_are_added_to_cross_site_403(
    client: TestClient,
) -> None:
    """
    Verify the other BrowserTrustBoundaryMiddleware
    short-circuit path.

    Sec-Fetch-Site: cross-site rejects the unsafe request
    before route processing.
    """

    response = client.post(
        TOKEN_PATH,
        data={
            "username": (
                "missing@example.com"
            ),
            "password": (
                "WrongPassword123!"
            ),
        },
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "Cross-site state-changing "
            "request rejected."
        )
    }

    assert_security_headers(
        response
    )


# =========================================================
# CORS INTERACTION
# =========================================================


def test_security_headers_coexist_with_cors_headers(
    client: TestClient,
) -> None:
    """
    CORS and response hardening serve different purposes and
    must coexist on the same response.
    """

    response = client.get(
        HEALTH_PATH,
        headers={
            "Origin": (
                settings.frontend_origin
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert_security_headers(
        response
    )

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        == settings.frontend_origin
    )

    assert (
        response.headers.get(
            "access-control-allow-credentials"
        )
        == "true"
    )


def test_security_headers_are_added_to_cors_preflight(
    client: TestClient,
) -> None:
    """
    CORSMiddleware may generate the OPTIONS response itself.

    Because SecurityHeadersMiddleware is outermost, the
    preflight response should still receive the baseline
    response security policy.
    """

    response = client.options(
        REFRESH_PATH,
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Access-Control-Request-Method": (
                "POST"
            ),
            "Access-Control-Request-Headers": (
                settings.csrf_header_name
            ),
        },
    )

    assert (
        response.status_code
        == 200
    ), response.text

    assert_security_headers(
        response
    )

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        == settings.frontend_origin
    )

    allowed_headers = (
        response.headers.get(
            "access-control-allow-headers",
            ""
        )
        .lower()
    )

    assert (
        settings.csrf_header_name.lower()
        in allowed_headers
    )


# =========================================================
# HSTS — DEVELOPMENT
# =========================================================


def test_hsts_is_not_added_outside_production(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    HSTS must not be forced onto localhost HTTP development.

    The middleware derives this behavior from
    settings.is_production.
    """

    monkeypatch.setattr(
        settings,
        "app_env",
        "development",
    )

    response = client.get(
        HEALTH_PATH
    )

    assert (
        response.status_code
        == 200
    )

    assert_security_headers(
        response
    )

    assert (
        response.headers.get(
            "strict-transport-security"
        )
        is None
    )


# =========================================================
# HSTS — PRODUCTION
# =========================================================


def test_hsts_is_added_in_production(
    client: TestClient,
    monkeypatch,
) -> None:
    """
    Production responses must advertise the configured HSTS
    policy.
    """

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        HEALTH_PATH
    )

    assert (
        response.status_code
        == 200
    )

    assert_security_headers(
        response
    )

    assert (
        response.headers.get(
            "strict-transport-security"
        )
        == EXPECTED_HSTS
    )