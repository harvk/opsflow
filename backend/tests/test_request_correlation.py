from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import (
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

from app.core.request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    get_request_id,
    reset_request_id,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)


def build_test_application(
) -> FastAPI:
    application = (
        FastAPI()
    )

    @application.get(
        "/request-id"
    )
    async def request_id_echo(
    ) -> dict[str, str | None]:
        return {
            "requestId": (
                get_request_id()
            )
        }

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    return application


def assert_uuid4(
    value: str,
) -> None:
    parsed = UUID(
        value
    )

    assert str(parsed) == value
    assert parsed.version == 4


def test_missing_request_id_generates_uuid4(
) -> None:
    application = (
        build_test_application()
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/request-id"
        )

    assert response.status_code == 200

    response_request_id = (
        response.headers[
            REQUEST_ID_HEADER
        ]
    )

    assert_uuid4(
        response_request_id
    )

    assert response.json() == {
        "requestId": (
            response_request_id
        )
    }


def test_safe_upstream_request_id_is_preserved(
) -> None:
    application = (
        build_test_application()
    )

    supplied_request_id = (
        "edge.request:9.6.4-001"
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/request-id",
            headers={
                REQUEST_ID_HEADER: (
                    supplied_request_id
                )
            },
        )

    assert response.status_code == 200

    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == supplied_request_id
    )

    assert response.json() == {
        "requestId": (
            supplied_request_id
        )
    }


def test_invalid_upstream_request_id_is_replaced(
) -> None:
    application = (
        build_test_application()
    )

    supplied_request_id = (
        "request id contains spaces"
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/request-id",
            headers={
                REQUEST_ID_HEADER: (
                    supplied_request_id
                )
            },
        )

    generated_request_id = (
        response.headers[
            REQUEST_ID_HEADER
        ]
    )

    assert generated_request_id != (
        supplied_request_id
    )

    assert_uuid4(
        generated_request_id
    )

    assert response.json() == {
        "requestId": (
            generated_request_id
        )
    }


def test_request_context_is_reset_after_response(
) -> None:
    application = (
        build_test_application()
    )

    assert get_request_id() is None

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/request-id"
        )

    assert response.status_code == 200
    assert get_request_id() is None


def test_request_context_is_isolated_between_tasks(
) -> None:
    async def observe_request_id(
        request_id: str,
    ) -> str | None:
        token = bind_request_id(
            request_id
        )

        try:
            await asyncio.sleep(
                0
            )

            return get_request_id()

        finally:
            reset_request_id(
                token
            )

    async def run_concurrently(
    ) -> list[str | None]:
        return list(
            await asyncio.gather(
                observe_request_id(
                    "request-one"
                ),
                observe_request_id(
                    "request-two"
                ),
            )
        )

    observed_request_ids = (
        asyncio.run(
            run_concurrently()
        )
    )

    assert observed_request_ids == [
        "request-one",
        "request-two",
    ]

    assert get_request_id() is None