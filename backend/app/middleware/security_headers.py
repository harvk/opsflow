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

from app.core.config import (
    settings,
)


# =========================================================
# BASELINE RESPONSE SECURITY POLICY
# =========================================================


BASE_SECURITY_HEADERS: tuple[
    tuple[str, str],
    ...,
] = (
    (
        "X-Content-Type-Options",
        "nosniff",
    ),
    (
        "X-Frame-Options",
        "DENY",
    ),
    (
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    ),
    (
        "Permissions-Policy",
        (
            "camera=(), "
            "microphone=(), "
            "geolocation=()"
        ),
    ),
    (
        "X-Permitted-Cross-Domain-Policies",
        "none",
    ),
)


HSTS_HEADER_NAME = (
    "Strict-Transport-Security"
)

HSTS_HEADER_VALUE = (
    "max-age=31536000; "
    "includeSubDomains"
)


# =========================================================
# SECURITY HEADERS MIDDLEWARE
# =========================================================


class SecurityHeadersMiddleware:
    """
    Add baseline defensive HTTP response headers to OpsFlow
    responses.

    The middleware operates at the ASGI response boundary,
    allowing the same policy to apply to responses produced
    by:

        API routes
        authentication failures
        validation failures
        CORS middleware
        browser-trust middleware
        framework-generated 404 responses

    Content-Security-Policy is intentionally not added yet.

    FastAPI's Swagger and ReDoc interfaces require a CSP
    designed specifically for their scripts, styles, and
    resources.

    Strict-Transport-Security is enabled only when OpsFlow
    runs in the production environment because HSTS applies
    to HTTPS deployments and should not be forced onto local
    HTTP development.
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
        """
        Apply security headers to HTTP responses.

        Non-HTTP ASGI scopes, such as WebSocket traffic, are
        passed through unchanged.
        """

        if (
            scope["type"]
            != "http"
        ):
            await self.app(
                scope,
                receive,
                send,
            )

            return

        async def send_with_security_headers(
            message: Message,
        ) -> None:
            """
            Intercept the response-start event before headers
            are transmitted to the client.
            """

            if (
                message["type"]
                == "http.response.start"
            ):
                headers = (
                    MutableHeaders(
                        scope=message
                    )
                )

                # -----------------------------------------
                # Baseline policy
                # -----------------------------------------

                for (
                    header_name,
                    header_value,
                ) in BASE_SECURITY_HEADERS:
                    headers[
                        header_name
                    ] = header_value

                # -----------------------------------------
                # Production HTTPS policy
                # -----------------------------------------
                #
                # Do not emit HSTS during localhost HTTP
                # development.
                #
                # settings.is_production is the existing
                # authoritative environment switch.

                if (
                    settings.is_production
                ):
                    headers[
                        HSTS_HEADER_NAME
                    ] = (
                        HSTS_HEADER_VALUE
                    )

            await send(
                message
            )

        await self.app(
            scope,
            receive,
            send_with_security_headers,
        )