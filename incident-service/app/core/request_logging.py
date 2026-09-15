from __future__ import annotations

import json
import logging
from datetime import (
    UTC,
    datetime,
)
from typing import (
    Literal,
)

from app.core.logging_config import (
    REQUEST_LOGGER_NAME,
)
from app.core.request_context import (
    get_request_id,
)

HttpRequestEventName = Literal[
    "http_request_completed",
    "http_request_failed",
]

_request_logger = logging.getLogger(
    REQUEST_LOGGER_NAME
)


def emit_http_request_event(
    *,
    event: HttpRequestEventName,
    service_name: str,
    environment: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    exception_type: str | None = None,
) -> None:
    """
    Emit one structured HTTP request event.

    Deliberately excluded data includes:

        authorization headers
        cookies
        internal service credentials
        CSRF tokens
        raw query strings
        request and response bodies
        exception messages

    exception_type contains only the exception class name.
    """

    level = (
        "ERROR"
        if event
        == "http_request_failed"
        else "INFO"
    )

    request_id = (
        get_request_id()
        or "unavailable"
    )

    payload: dict[
        str,
        object,
    ] = {
        "timestamp": (
            datetime
            .now(UTC)
            .isoformat()
            .replace(
                "+00:00",
                "Z",
            )
        ),
        "level": level,
        "event": event,
        "service": service_name,
        "environment": environment,
        "requestId": request_id,
        "method": method,
        "path": path,
        "statusCode": status_code,
        "durationMs": round(
            max(
                duration_ms,
                0.0,
            ),
            3,
        ),
    }

    if exception_type is not None:
        payload[
            "exceptionType"
        ] = exception_type

    message = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(
            ",",
            ":",
        ),
        sort_keys=True,
    )

    if (
        event
        == "http_request_failed"
    ):
        _request_logger.error(
            message
        )

        return

    _request_logger.info(
        message
    )