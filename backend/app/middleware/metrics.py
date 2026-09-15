from __future__ import annotations

from time import (
    monotonic,
)

from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from app.core.metrics import (
    OperationalMetrics,
)


def _normalized_route(
    scope: Scope,
) -> str:
    """
    Return the matched FastAPI route template.

    A concrete path such as:

        /api/v1/incidents/123

    must be recorded as:

        /api/v1/incidents/{incident_id}

    This prevents resource identifiers from creating an
    unbounded number of Prometheus label combinations.
    """

    route = scope.get(
        "route"
    )

    route_path = getattr(
        route,
        "path",
        None,
    )

    if isinstance(
        route_path,
        str,
    ):
        return route_path

    return "__unmatched__"


class MetricsMiddleware:
    """
    Measure inbound HTTP request count and duration.

    Pure ASGI middleware captures streaming-response duration
    and avoids BaseHTTPMiddleware context propagation issues.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics: OperationalMetrics,
    ) -> None:
        self.app = app
        self._metrics = metrics

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope[
            "type"
        ] != "http":
            await self.app(
                scope,
                receive,
                send,
            )

            return

        started_at = (
            monotonic()
        )

        status_code = 500

        async def send_with_status(
            message: Message,
        ) -> None:
            nonlocal status_code

            if (
                message[
                    "type"
                ]
                == "http.response.start"
            ):
                status_code = int(
                    message[
                        "status"
                    ]
                )

            await send(
                message
            )

        try:
            await self.app(
                scope,
                receive,
                send_with_status,
            )

        finally:
            self._metrics.observe_http_request(
                method=str(
                    scope.get(
                        "method",
                        "UNKNOWN",
                    )
                ),
                route=(
                    _normalized_route(
                        scope
                    )
                ),
                status_code=status_code,
                duration_seconds=(
                    monotonic()
                    - started_at
                ),
            )