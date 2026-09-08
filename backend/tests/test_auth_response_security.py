from fastapi.testclient import (
    TestClient,
)


AUTH_CACHE_CONTROL = (
    "no-store, "
    "no-cache, "
    "must-revalidate"
)


# =========================================================
# ASSERTION HELPERS
# =========================================================


def assert_auth_response_not_cacheable(
    response,
) -> None:
    assert (
        response.headers.get(
            "Cache-Control"
        )
        == AUTH_CACHE_CONTROL
    )

    assert (
        response.headers.get(
            "Pragma"
        )
        == "no-cache"
    )


def assert_baseline_security_headers(
    response,
) -> None:
    assert (
        response.headers.get(
            "X-Content-Type-Options"
        )
        == "nosniff"
    )

    assert (
        response.headers.get(
            "X-Frame-Options"
        )
        == "DENY"
    )

    assert (
        response.headers.get(
            "Referrer-Policy"
        )
        == (
            "strict-origin-when-cross-origin"
        )
    )

    assert (
        response.headers.get(
            "Permissions-Policy"
        )
        == (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        )
    )

    assert (
        response.headers.get(
            "X-Permitted-Cross-Domain-Policies"
        )
        == "none"
    )


# =========================================================
# SUCCESS RESPONSES
# =========================================================


def test_authenticated_auth_response_is_not_cacheable(
    client: TestClient,
    auth_headers: dict[
        str,
        str,
    ],
) -> None:
    """
    /me does not itself need to know about HTTP cache
    policy.

    The response boundary must enforce the invariant.
    """

    response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers,
    )

    assert (
        response.status_code
        == 200
    )

    assert_auth_response_not_cacheable(
        response
    )


# =========================================================
# AUTHENTICATION DEPENDENCY FAILURES
# =========================================================


def test_missing_bearer_token_response_is_not_cacheable(
    client: TestClient,
) -> None:
    """
    OAuth2PasswordBearer can reject the request before the
    route body executes.

    The middleware must still apply the auth cache policy.
    """

    response = client.get(
        "/api/v1/auth/me"
    )

    assert (
        response.status_code
        == 401
    )

    assert_auth_response_not_cacheable(
        response
    )

    assert (
        response.headers.get(
            "WWW-Authenticate"
        )
        == "Bearer"
    )


# =========================================================
# FRAMEWORK VALIDATION FAILURES
# =========================================================


def test_auth_validation_error_is_not_cacheable(
    client: TestClient,
) -> None:
    """
    Invalid request bodies generate a FastAPI 422 before
    route business logic executes.

    They still belong to the authentication response
    boundary.
    """

    response = client.post(
        (
            "/api/v1/auth/"
            "password-reset/request"
        ),
        json={},
    )

    assert (
        response.status_code
        == 422
    )

    assert_auth_response_not_cacheable(
        response
    )


# =========================================================
# BROWSER TRUST REJECTIONS
# =========================================================


def test_browser_trust_auth_rejection_is_not_cacheable(
    client: TestClient,
) -> None:
    """
    BrowserTrustBoundaryMiddleware can terminate the request
    before FastAPI reaches the route.

    SecurityHeadersMiddleware must remain outside that
    boundary so the rejection receives the same response
    protections.
    """

    response = client.post(
        (
            "/api/v1/auth/"
            "password-reset/request"
        ),
        json={
            "email": (
                "blocked@example.com"
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

    assert_auth_response_not_cacheable(
        response
    )

    assert_baseline_security_headers(
        response
    )


# =========================================================
# BASELINE SECURITY HEADERS
# =========================================================


def test_auth_framework_error_keeps_baseline_security_headers(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/auth/me"
    )

    assert (
        response.status_code
        == 401
    )

    assert_baseline_security_headers(
        response
    )


# =========================================================
# NON-AUTH ROUTES
# =========================================================


def test_non_auth_response_is_not_forced_into_auth_cache_policy(
    client: TestClient,
) -> None:
    """
    The authentication-specific cache policy must not
    silently become a global application cache policy.

    Other endpoints can receive their own caching semantics
    independently.
    """

    response = client.get(
        "/api/v1/health"
    )

    assert (
        response.status_code
        == 200
    )

    cache_control = (
        response.headers.get(
            "Cache-Control",
            "",
        )
        .lower()
    )

    assert (
        "no-store"
        not in cache_control
    )

    # The generic security-header boundary still applies.
    assert_baseline_security_headers(
        response
    )
    
def test_auth_route_not_found_response_is_not_cacheable(
    client: TestClient,
) -> None:
    """
    Even a framework-generated 404 inside the authentication
    URL boundary must inherit the authentication cache
    policy.

    No authentication route function executes in this case,
    proving that middleware owns the policy.
    """

    response = client.get(
        "/api/v1/auth/route-that-does-not-exist"
    )

    assert (
        response.status_code
        == 404
    )

    assert_auth_response_not_cacheable(
        response
    )

    assert_baseline_security_headers(
        response
    )
    
def test_similar_non_auth_path_is_not_treated_as_auth_boundary(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/authentication"
    )

    assert (
        response.status_code
        == 404
    )

    cache_control = (
        response.headers.get(
            "Cache-Control",
            "",
        )
        .lower()
    )

    assert (
        "no-store"
        not in cache_control
    )

    assert_baseline_security_headers(
        response
    )