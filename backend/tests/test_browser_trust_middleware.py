from fastapi import (
    FastAPI,
)

from fastapi.testclient import (
    TestClient,
)

from app.core.config import (
    settings,
)

from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)


# =========================================================
# TEST APPLICATION
# =========================================================


def create_browser_trust_test_app() -> FastAPI:
    """
    Create a deliberately tiny application containing only
    BrowserTrustBoundaryMiddleware.

    These tests isolate middleware behavior from:

        authentication
        CSRF validation
        CORS
        database access
        application repositories

    Integration behavior remains covered separately by
    test_browser_boundary.py.
    """

    application = FastAPI()

    application.add_middleware(
        BrowserTrustBoundaryMiddleware,
        allowed_origins=[
            settings.frontend_origin,
        ],
    )

    @application.get(
        "/resource",
    )
    def read_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    @application.post(
        "/resource",
    )
    def create_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    @application.put(
        "/resource",
    )
    def replace_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    @application.patch(
        "/resource",
    )
    def update_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    @application.delete(
        "/resource",
    )
    def delete_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    @application.options(
        "/resource",
    )
    def options_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    return application


# =========================================================
# TRUSTED ORIGIN
# =========================================================


def test_trusted_frontend_origin_can_post() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "ok": True
    }


def test_trusted_frontend_origin_can_put() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.put(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert response.status_code == 200


def test_trusted_frontend_origin_can_patch() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.patch(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert response.status_code == 200


def test_trusted_frontend_origin_can_delete() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.delete(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Sec-Fetch-Site": (
                "same-site"
            ),
        },
    )

    assert response.status_code == 200


# =========================================================
# FETCH METADATA
# =========================================================


def test_cross_site_post_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Cross-site state-changing "
            "request rejected."
        )
    }


def test_cross_site_put_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.put(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 403


def test_cross_site_patch_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.patch(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 403


def test_cross_site_delete_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.delete(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 403


# =========================================================
# SAFE METHODS
# =========================================================


def test_cross_site_get_is_not_blocked() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.get(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "ok": True
    }


def test_options_is_not_treated_as_unsafe() -> None:
    """
    OPTIONS must be allowed through the browser-trust layer.

    In the real application CORSMiddleware consumes browser
    preflight requests after this middleware allows them to
    continue.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.options(
        "/resource",
        headers={
            "Sec-Fetch-Site": (
                "cross-site"
            ),
        },
    )

    assert response.status_code == 200


# =========================================================
# UNTRUSTED ORIGIN
# =========================================================


def test_untrusted_origin_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                "https://evil.example"
            ),
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Request origin is not trusted."
        )
    }


def test_untrusted_origin_is_rejected_even_without_fetch_metadata() -> None:
    """
    Origin validation is independent of Sec-Fetch-Site.

    An attacker cannot evade the trust boundary merely by
    omitting Fetch Metadata.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                "https://attacker.example"
            ),
        },
    )

    assert response.status_code == 403


# =========================================================
# SAME-ORIGIN API REQUESTS
# =========================================================


def test_same_origin_api_request_is_allowed() -> None:
    """
    FastAPI-hosted tools such as Swagger may originate from
    the API host itself.

    BrowserTrustBoundaryMiddleware explicitly allows genuine
    same-origin requests even though that origin is not the
    React frontend origin.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                "http://testserver"
            ),
            "Sec-Fetch-Site": (
                "same-origin"
            ),
        },
    )

    assert response.status_code == 200


# =========================================================
# REFERER FALLBACK
# =========================================================


def test_trusted_referer_is_allowed() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Referer": (
                f"{settings.frontend_origin}"
                "/dashboard"
            ),
        },
    )

    assert response.status_code == 200


def test_untrusted_referer_is_rejected() -> None:
    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Referer": (
                "https://evil.example/"
                "attack"
            ),
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Request referer is not trusted."
        )
    }


def test_malformed_referer_is_rejected() -> None:
    """
    A Referer without a valid scheme + network location
    cannot establish browser trust.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Referer": (
                "not-a-valid-origin"
            ),
        },
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "Request referer is not trusted."
        )
    }


# =========================================================
# ORIGIN PRECEDENCE
# =========================================================


def test_untrusted_origin_is_not_rescued_by_trusted_referer() -> None:
    """
    If Origin exists, it is authoritative.

    A malicious Origin must not become trusted merely because
    the request also supplies a trusted-looking Referer.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                "https://evil.example"
            ),
            "Referer": (
                f"{settings.frontend_origin}"
                "/dashboard"
            ),
        },
    )

    assert response.status_code == 403


def test_trusted_origin_takes_precedence_over_untrusted_referer() -> None:
    """
    BrowserTrustBoundaryMiddleware evaluates Referer only
    when Origin is absent.

    Once a valid Origin establishes browser trust, the
    request may continue.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
            "Referer": (
                "https://evil.example/"
                "attack"
            ),
        },
    )

    assert response.status_code == 200


# =========================================================
# NON-BROWSER CLIENTS
# =========================================================


def test_request_without_browser_metadata_is_allowed() -> None:
    """
    Non-browser clients may not send:

        Origin
        Referer
        Sec-Fetch-Site

    BrowserTrustBoundaryMiddleware deliberately permits those
    requests to continue.

    Authentication and authorization remain the
    responsibility of the target API route.
    """

    client = TestClient(
        create_browser_trust_test_app()
    )

    response = client.post(
        "/resource"
    )

    assert response.status_code == 200


# =========================================================
# CONFIGURATION HARDENING
# =========================================================


def test_single_string_allowed_origin_is_supported() -> None:
    """
    The middleware protects against a common Python
    configuration mistake:

        allowed_origins="http://..."

    rather than:

        allowed_origins=["http://..."]

    A string is normalized into a one-item collection rather
    than being interpreted as an iterable of characters.
    """

    application = FastAPI()

    application.add_middleware(
        BrowserTrustBoundaryMiddleware,
        allowed_origins=(
            settings.frontend_origin
        ),
    )

    @application.post(
        "/resource",
    )
    def create_resource() -> dict[str, bool]:
        return {
            "ok": True
        }

    client = TestClient(
        application
    )

    response = client.post(
        "/resource",
        headers={
            "Origin": (
                settings.frontend_origin
            ),
        },
    )

    assert response.status_code == 200