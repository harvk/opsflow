from __future__ import annotations

from starlette.datastructures import (
    Headers,
    MutableHeaders,
)
from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from app.core.request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    reset_request_id,
    resolve_request_id,
)


class RequestCorrelationMiddleware:
    """
    Establish one request identifier for an HTTP operation.

    The identifier is available through the request ContextVar
    while application code is running and is returned on the
    response as X-Request-ID.

    Pure ASGI middleware is used so the request context remains
    well-defined across asynchronous request handling and
    streaming responses.
    """

    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

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

        request_headers = Headers(
            scope=scope
        )

        request_id = resolve_request_id(
            request_headers.get(
                REQUEST_ID_HEADER
            )
        )

        context_token = bind_request_id(
            request_id
        )

        async def send_with_request_id(
            message: Message,
        ) -> None:
            if (
                message["type"]
                == "http.response.start"
            ):
                response_headers = (
                    MutableHeaders(
                        scope=message
                    )
                )

                response_headers[
                    REQUEST_ID_HEADER
                ] = request_id

            await send(
                message
            )

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )

        finally:
            reset_request_id(
                context_token
            )