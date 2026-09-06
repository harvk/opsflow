from starlette.datastructures import (
    MutableHeaders,
)

from starlette.types import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
)

from app.core.config import settings


class SecurityHeadersMiddleware:
    """
    Adds baseline defensive HTTP response headers
    to OpsFlow API responses.

    This middleware intentionally does not add a
    Content-Security-Policy yet because FastAPI's
    development Swagger/Redoc interfaces require
    a CSP designed specifically for those pages.

    HSTS is enabled only in production because it
    applies to HTTPS deployments.
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

        async def send_with_security_headers(
            message: Message,
        ) -> None:
            if (
                message["type"]
                == "http.response.start"
            ):
                headers = MutableHeaders(
                    scope=message
                )

                # Prevent MIME-type sniffing.
                headers[
                    "X-Content-Type-Options"
                ] = "nosniff"

                # Prevent the API/docs from being
                # embedded in arbitrary frames.
                headers[
                    "X-Frame-Options"
                ] = "DENY"

                # Limit referrer information sent
                # across origins.
                headers[
                    "Referrer-Policy"
                ] = (
                    "strict-origin-when-cross-origin"
                )

                # OpsFlow currently has no reason to
                # expose these browser capabilities.
                headers[
                    "Permissions-Policy"
                ] = (
                    "camera=(), "
                    "microphone=(), "
                    "geolocation=()"
                )

                # Prevent Adobe/legacy cross-domain
                # policy files from relaxing access.
                headers[
                    "X-Permitted-Cross-Domain-Policies"
                ] = "none"

                # HSTS belongs on HTTPS production
                # responses, not localhost HTTP.
                if settings.is_production:
                    headers[
                        "Strict-Transport-Security"
                    ] = (
                        "max-age=31536000; "
                        "includeSubDomains"
                    )

            await send(
                message
            )

        await self.app(
            scope,
            receive,
            send_with_security_headers,
        )