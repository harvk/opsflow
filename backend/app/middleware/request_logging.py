from __future__ import annotations

from time import (
    perf_counter,
)

from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from app.core.request_logging import (
    emit_http_request_event,
)


class RequestLoggingMiddleware:
    """
    Emit one structured log event for every HTTP request.

    This middleware is positioned inside request correlation,
    ensuring that the current request ID is available through
    the request ContextVar.

    Pure ASGI middleware avoids BaseHTTPMiddleware context and
    streaming-response limitations.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        service_name: str,
        environment: str,
    ) -> None:
        self.app = app
        self.service_name = (
            service_name
        )
        self.environment = (
            environment
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(
                scope,
                receive,
                send,
            )

            return

        started_at = (
            perf_counter()
        )

        response_status: (
            int | None
        ) = None

        async def send_with_status(
            message: Message,
        ) -> None:
            nonlocal response_status

            if (
                message["type"]
                == "http.response.start"
            ):
                response_status = int(
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

        except Exception as exc:
            emit_http_request_event(
                event=(
                    "http_request_failed"
                ),
                service_name=(
                    self.service_name
                ),
                environment=(
                    self.environment
                ),
                method=(
                    self._request_method(
                        scope
                    )
                ),
                path=(
                    self._request_path(
                        scope
                    )
                ),
                status_code=(
                    response_status
                    or 500
                ),
                duration_ms=(
                    self._duration_ms(
                        started_at
                    )
                ),
                exception_type=(
                    type(exc).__name__
                ),
            )

            raise

        emit_http_request_event(
            event=(
                "http_request_completed"
            ),
            service_name=(
                self.service_name
            ),
            environment=(
                self.environment
            ),
            method=(
                self._request_method(
                    scope
                )
            ),
            path=(
                self._request_path(
                    scope
                )
            ),
            status_code=(
                response_status
                or 500
            ),
            duration_ms=(
                self._duration_ms(
                    started_at
                )
            ),
        )

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        return (
            perf_counter()
            - started_at
        ) * 1000

    @staticmethod
    def _request_method(
        scope: Scope,
    ) -> str:
        method = scope.get(
            "method",
            "UNKNOWN",
        )

        if not isinstance(
            method,
            str,
        ):
            return "UNKNOWN"

        return method.upper()

    @staticmethod
    def _request_path(
        scope: Scope,
    ) -> str:
        """
        Prefer the registered route template after routing.

        For example:

            /api/v1/incidents/{incident_id}

        is safer and more useful than logging a different raw
        UUID path for every request.

        Requests that never reach a registered route, such as
        middleware rejections and 404 responses, fall back to
        scope["path"]. Query strings are never included.
        """

        route = scope.get(
            "route"
        )

        route_path = getattr(
            route,
            "path",
            None,
        )

        if (
            isinstance(
                route_path,
                str,
            )
            and route_path
        ):
            return route_path

        request_path = scope.get(
            "path",
            ""
        )

        if not isinstance(
            request_path,
            str,
        ):
            return ""

        return request_path