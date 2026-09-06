from fastapi.testclient import (
    TestClient,
)

from app.core.config import settings


def assert_baseline_security_headers(
    response,
) -> None:
    assert (
        response.headers[
            "x-content-type-options"
        ]
        == "nosniff"
    )

    assert (
        response.headers[
            "x-frame-options"
        ]
        == "DENY"
    )

    assert (
        response.headers[
            "referrer-policy"
        ]
        == (
            "strict-origin-when-cross-origin"
        )
    )

    assert (
        response.headers[
            "permissions-policy"
        ]
        == (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        )
    )

    assert (
        response.headers[
            "x-permitted-cross-domain-policies"
        ]
        == "none"
    )


def test_security_headers_are_added_to_success_response(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/health"
    )

    assert response.status_code == 200

    assert_baseline_security_headers(
        response
    )


def test_security_headers_are_added_to_unauthorized_response(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/services"
    )

    assert response.status_code == 401

    assert_baseline_security_headers(
        response
    )


def test_hsts_is_not_added_in_development(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "app_env",
        "development",
    )

    response = client.get(
        "/api/v1/health"
    )

    assert (
        "strict-transport-security"
        not in response.headers
    )


def test_hsts_is_added_in_production(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        "/api/v1/health"
    )

    assert (
        response.headers[
            "strict-transport-security"
        ]
        == (
            "max-age=31536000; "
            "includeSubDomains"
        )
    )