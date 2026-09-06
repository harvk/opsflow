from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)


def create_test_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(
        BrowserTrustBoundaryMiddleware,
        allowed_origins=[
            "http://localhost:5173",
        ],
    )

    @app.get("/resource")
    def read_resource() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/resource")
    def mutate_resource() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_trusted_origin_can_make_post_request() -> None:
    client = TestClient(create_test_app())

    response = client.post(
        "/resource",
        headers={
            "Origin": "http://localhost:5173",
            "Sec-Fetch-Site": "same-site",
        },
    )

    assert response.status_code == 200


def test_untrusted_origin_is_rejected() -> None:
    client = TestClient(create_test_app())

    response = client.post(
        "/resource",
        headers={
            "Origin": "https://evil.example",
        },
    )

    assert response.status_code == 403


def test_cross_site_mutation_is_rejected() -> None:
    client = TestClient(create_test_app())

    response = client.post(
        "/resource",
        headers={
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 403


def test_cross_site_get_is_not_blocked_by_mutation_policy() -> None:
    client = TestClient(create_test_app())

    response = client.get(
        "/resource",
        headers={
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 200


def test_non_browser_client_without_origin_is_allowed() -> None:
    client = TestClient(create_test_app())

    response = client.post("/resource")

    assert response.status_code == 200


def test_untrusted_referer_is_rejected() -> None:
    client = TestClient(create_test_app())

    response = client.post(
        "/resource",
        headers={
            "Referer": "https://evil.example/attack",
        },
    )

    assert response.status_code == 403