from fastapi.testclient import TestClient

from app.core.config import (
    settings,
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


# =========================================================
# REQUEST CONSTANTS
# =========================================================


UNTRUSTED_ORIGIN = (
    "https://evil.example"
)

UNTRUSTED_REFERER = (
    "https://evil.example/attack"
)

INVALID_LOGIN_DATA = {
    "username": (
        "does-not-exist@example.com"
    ),
    "password": (
        "DefinitelyWrongPassword!"
    ),
}


# =========================================================
# FETCH METADATA
# =========================================================


def test_cross_site_post_is_rejected(
    client: TestClient,
) -> None:
    """
    A browser explicitly identifying an unsafe request as
    cross-site must be rejected before the authentication
    route processes it.

    If the request reached /auth/token normally, the invalid
    credentials below would produce HTTP 401.

    HTTP 403 therefore demonstrates that the browser trust
    boundary intercepted the request first.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
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


def test_cross_site_refresh_is_rejected_before_route(
    client: TestClient,
) -> None:
    """
    /auth/refresh normally returns HTTP 401 when no refresh
    cookie exists.

    Supplying Sec-Fetch-Site: cross-site should cause the
    browser trust middleware to reject the request first,
    producing HTTP 403 instead.
    """

    response = client.post(
        REFRESH_PATH,
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


def test_cross_site_get_is_not_blocked_by_mutation_policy(
    client: TestClient,
) -> None:
    """
    The browser trust policy protects unsafe state-changing
    operations.

    A GET request is not a state mutation and therefore
    should not be rejected merely because Fetch Metadata
    identifies it as cross-site.
    """

    response = client.get(
        HEALTH_PATH,
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )


# =========================================================
# ORIGIN VALIDATION
# =========================================================


def test_untrusted_origin_post_is_rejected(
    client: TestClient,
) -> None:
    """
    A state-changing browser request originating from a site
    other than the configured frontend must not reach the
    authentication route.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
        headers={
            "Origin": (
                UNTRUSTED_ORIGIN
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )


def test_untrusted_origin_refresh_is_rejected(
    client: TestClient,
) -> None:
    """
    An untrusted Origin must cause rejection before the
    refresh route can produce its normal missing-cookie 401.
    """

    response = client.post(
        REFRESH_PATH,
        headers={
            "Origin": (
                UNTRUSTED_ORIGIN
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )


def test_configured_frontend_origin_reaches_login_route(
    client: TestClient,
) -> None:
    """
    The configured React origin should pass the browser trust
    boundary.

    Credentials are intentionally invalid.

    Therefore the expected result is the route's normal 401,
    not middleware HTTP 403.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


def test_configured_frontend_origin_reaches_refresh_route(
    client: TestClient,
) -> None:
    """
    A trusted frontend request without a refresh cookie
    should pass the browser boundary and then fail at the
    authentication route itself.

    That route returns HTTP 401 for a missing refresh
    credential.
    """

    response = client.post(
        REFRESH_PATH,
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Could not refresh credentials."
        )
    }


# =========================================================
# SAME-ORIGIN API REQUESTS
# =========================================================


def test_api_same_origin_post_is_allowed_through_boundary(
    client: TestClient,
) -> None:
    """
    Requests originating from the API host itself should
    remain valid.

    Starlette TestClient uses testserver as its host.

    The deliberately invalid credentials confirm that the
    request reached the authentication route because the
    route responds with HTTP 401.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
        headers={
            "Origin": (
                "http://testserver"
            ),
            "Sec-Fetch-Site": (
                "same-origin"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


# =========================================================
# REFERER FALLBACK
# =========================================================


def test_trusted_referer_is_allowed_when_origin_is_missing(
    client: TestClient,
) -> None:
    """
    When Origin is unavailable, the configured frontend
    Referer should be accepted as the browser trust fallback.

    Invalid credentials then produce the route's normal 401.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
        headers={
            "Referer": (
                f"{settings.frontend_origin}/login"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


def test_untrusted_referer_is_rejected_when_origin_is_missing(
    client: TestClient,
) -> None:
    """
    An unsafe request with no Origin but an explicitly
    untrusted Referer must be rejected.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
        headers={
            "Referer": (
                UNTRUSTED_REFERER
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )


# =========================================================
# NON-BROWSER CLIENT COMPATIBILITY
# =========================================================


def test_request_without_browser_metadata_reaches_route(
    client: TestClient,
) -> None:
    """
    pytest, curl, backend services, and other non-browser API
    clients may not supply Origin, Referer, or Fetch Metadata.

    The browser trust middleware should therefore allow the
    request to reach normal route-level authentication.

    Invalid login credentials should produce 401 rather than
    middleware 403.
    """

    response = client.post(
        TOKEN_PATH,
        data=INVALID_LOGIN_DATA,
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


# =========================================================
# CORS — TRUSTED SIMPLE REQUEST
# =========================================================


def test_trusted_origin_receives_cors_response_headers(
    client: TestClient,
) -> None:
    """
    A normal request from the configured React frontend
    should receive an explicit Access-Control-Allow-Origin
    response and permission to use credentials.
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


def test_untrusted_simple_get_does_not_receive_cors_permission(
    client: TestClient,
) -> None:
    """
    CORS does not necessarily turn an ordinary server-side
    GET into HTTP 403.

    Instead, the server may still produce the resource while
    withholding Access-Control-Allow-Origin.

    A browser then refuses to expose that response to the
    attacking JavaScript.
    """

    response = client.get(
        HEALTH_PATH,
        headers={
            "Origin": (
                UNTRUSTED_ORIGIN
            ),
        },
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        is None
    )


# =========================================================
# CORS PREFLIGHT — TRUSTED FRONTEND
# =========================================================


def test_trusted_csrf_preflight_is_allowed(
    client: TestClient,
) -> None:
    """
    The React frontend must be permitted to send the custom
    CSRF header on POST requests.

    A browser performs this OPTIONS preflight before some
    credentialed cross-origin requests.
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

    allowed_methods = (
        response.headers.get(
            "access-control-allow-methods",
            "",
        )
        .upper()
    )

    assert (
        "POST"
        in allowed_methods
    )

    allowed_headers = (
        response.headers.get(
            "access-control-allow-headers",
            "",
        )
        .lower()
    )

    assert (
        settings.csrf_header_name.lower()
        in allowed_headers
    )


def test_options_preflight_is_not_blocked_as_unsafe_request(
    client: TestClient,
) -> None:
    """
    OPTIONS must reach CORS middleware instead of being
    treated as a state-changing application operation.

    Otherwise the browser could never negotiate permission
    to send X-CSRF-Token.
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
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert (
        response.status_code
        == 200
    ), response.text


# =========================================================
# CORS PREFLIGHT — UNTRUSTED ORIGIN
# =========================================================


def test_untrusted_origin_preflight_is_rejected(
    client: TestClient,
) -> None:
    """
    The API must not grant an arbitrary website permission to
    perform credentialed POST requests using the CSRF header.
    """

    response = client.options(
        REFRESH_PATH,
        headers={
            "Origin": (
                UNTRUSTED_ORIGIN
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
        == 400
    )

    assert (
        response.headers.get(
            "access-control-allow-origin"
        )
        is None
    )


# =========================================================
# CORS POLICY REGRESSION
# =========================================================


def test_cors_does_not_use_wildcard_for_credentialed_origin(
    client: TestClient,
) -> None:
    """
    Credentialed browser authentication should explicitly
    identify the trusted React origin rather than returning
    a wildcard origin.
    """

    response = client.get(
        HEALTH_PATH,
        headers={
            "Origin": (
                settings.frontend_origin
            ),
        },
    )

    allow_origin = (
        response.headers.get(
            "access-control-allow-origin"
        )
    )

    assert (
        allow_origin
        == settings.frontend_origin
    )

    assert (
        allow_origin
        != "*"
    )