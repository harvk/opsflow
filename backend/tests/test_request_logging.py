from __future__ import annotations

import json
from typing import (
    Any,
)

import pytest
from fastapi import (
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

import app.core.request_logging as request_logging_module
import app.middleware.request_logging as request_logging_middleware_module
from app.core.request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    reset_request_id,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)


class StubLogger:
    def __init__(
        self,
    ) -> None:
        self.info_messages: list[
            str
        ] = []

        self.error_messages: list[
            str
        ] = []

    def info(
        self,
        message: str,
    ) -> None:
        self.info_messages.append(
            message
        )

    def error(
        self,
        message: str,
    ) -> None:
        self.error_messages.append(
            message
        )


def build_test_application(
) -> FastAPI:
    application = (
        FastAPI()
    )

    @application.get(
        "/items/{item_id}"
    )
    async def get_item(
        item_id: str,
    ) -> dict[str, str]:
        return {
            "itemId": item_id
        }

    @application.get(
        "/failure"
    )
    async def fail_request(
    ) -> dict[str, str]:
        raise RuntimeError(
            "sensitive exception message"
        )

    application.add_middleware(
        RequestLoggingMiddleware,
        service_name=(
            "OpsFlow Test Service"
        ),
        environment="test",
    )

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    return application


def test_completed_event_is_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub_logger = (
        StubLogger()
    )

    monkeypatch.setattr(
        request_logging_module,
        "_request_logger",
        stub_logger,
    )

    context_token = bind_request_id(
        "json-event-request"
    )

    try:
        request_logging_module.emit_http_request_event(
            event=(
                "http_request_completed"
            ),
            service_name=(
                "OpsFlow Test Service"
            ),
            environment="test",
            method="GET",
            path="/api/v1/health",
            status_code=200,
            duration_ms=12.34567,
        )

    finally:
        reset_request_id(
            context_token
        )

    assert len(
        stub_logger.info_messages
    ) == 1

    assert (
        stub_logger.error_messages
        == []
    )

    payload = json.loads(
        stub_logger
        .info_messages[0]
    )

    assert payload[
        "event"
    ] == "http_request_completed"

    assert payload[
        "level"
    ] == "INFO"

    assert payload[
        "service"
    ] == "OpsFlow Test Service"

    assert payload[
        "environment"
    ] == "test"

    assert payload[
        "requestId"
    ] == "json-event-request"

    assert payload[
        "method"
    ] == "GET"

    assert payload[
        "path"
    ] == "/api/v1/health"

    assert payload[
        "statusCode"
    ] == 200

    assert payload[
        "durationMs"
    ] == 12.346

    assert payload[
        "timestamp"
    ].endswith(
        "Z"
    )

    assert (
        "exceptionType"
        not in payload
    )


def test_request_logging_uses_route_template_and_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_events: list[
        dict[str, Any]
    ] = []

    def capture_event(
        **event: Any,
    ) -> None:
        observed_events.append(
            event
        )

    monkeypatch.setattr(
        request_logging_middleware_module,
        "emit_http_request_event",
        capture_event,
    )

    application = (
        build_test_application()
    )

    request_id = (
        "structured-request:9.6.5"
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            (
                "/items/123"
                "?access_token=do-not-log"
            ),
            headers={
                REQUEST_ID_HEADER: (
                    request_id
                ),
                "Authorization": (
                    "Bearer do-not-log"
                ),
                "Cookie": (
                    "session=do-not-log"
                ),
            },
        )

    assert response.status_code == 200

    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == request_id
    )

    assert len(
        observed_events
    ) == 1

    event = (
        observed_events[0]
    )

    assert event[
        "event"
    ] == "http_request_completed"

    assert event[
        "service_name"
    ] == "OpsFlow Test Service"

    assert event[
        "environment"
    ] == "test"

    assert event[
        "method"
    ] == "GET"

    assert event[
        "path"
    ] == "/items/{item_id}"

    assert event[
        "status_code"
    ] == 200

    assert (
        event["duration_ms"]
        >= 0
    )

    serialized_event = (
        json.dumps(
            event
        )
    )

    assert (
        "do-not-log"
        not in serialized_event
    )


def test_not_found_response_is_logged_without_query_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_events: list[
        dict[str, Any]
    ] = []

    def capture_event(
        **event: Any,
    ) -> None:
        observed_events.append(
            event
        )

    monkeypatch.setattr(
        request_logging_middleware_module,
        "emit_http_request_event",
        capture_event,
    )

    application = (
        build_test_application()
    )

    with TestClient(
        application
    ) as client:
        response = client.get(

                "/missing"
                "?token=secret-query-value"

        )

    assert response.status_code == 404

    assert len(
        observed_events
    ) == 1

    event = (
        observed_events[0]
    )

    assert event[
        "event"
    ] == "http_request_completed"

    assert event[
        "path"
    ] == "/missing"

    assert event[
        "status_code"
    ] == 404

    assert (
        "secret-query-value"
        not in json.dumps(
            event
        )
    )


def test_unhandled_exception_logs_classification_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_events: list[
        dict[str, Any]
    ] = []

    def capture_event(
        **event: Any,
    ) -> None:
        observed_events.append(
            event
        )

    monkeypatch.setattr(
        request_logging_middleware_module,
        "emit_http_request_event",
        capture_event,
    )

    application = (
        build_test_application()
    )

    with TestClient(
        application,
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/failure",
            headers={
                REQUEST_ID_HEADER: (
                    "failed-request:9.6.5"
                )
            },
        )

    assert response.status_code == 500

    assert len(
        observed_events
    ) == 1

    event = (
        observed_events[0]
    )

    assert event[
        "event"
    ] == "http_request_failed"

    assert event[
        "path"
    ] == "/failure"

    assert event[
        "status_code"
    ] == 500

    assert event[
        "exception_type"
    ] == "RuntimeError"

    assert (
        "sensitive exception message"
        not in json.dumps(
            event
        )
    )