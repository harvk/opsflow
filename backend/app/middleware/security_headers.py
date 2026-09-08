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


AUTH_CACHE_CONTROL = (
    "no-store, "
    "no-cache, "
    "must-revalidate"
)


class SecurityHeadersMiddleware:
    """
    Apply baseline defensive HTTP headers to OpsFlow
    responses.

    Authentication responses receive an additional cache
    boundary.

    This is intentionally enforced at middleware level
    rather than relying only on individual routes because
    some responses can be generated before route code runs:

        request-validation failures
        authentication dependency failures
        middleware rejections
        framework-generated error responses

    HSTS remains production-only because local development
    uses plain HTTP.
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

        request_path = (
            scope.get(
                "path",
                "",
            )
        )

        auth_response = (
            self._is_auth_path(
                request_path
            )
        )

        async def send_with_security_headers(
            message: Message,
        ) -> None:
            if (
                message["type"]
                == "http.response.start"
            ):
                headers = (
                    MutableHeaders(
                        scope=message
                    )
                )

                # =========================================
                # BASELINE RESPONSE HARDENING
                # =========================================

                headers[
                    "X-Content-Type-Options"
                ] = "nosniff"

                headers[
                    "X-Frame-Options"
                ] = "DENY"

                headers[
                    "Referrer-Policy"
                ] = (
                    "strict-origin-when-cross-origin"
                )

                headers[
                    "Permissions-Policy"
                ] = (
                    "camera=(), "
                    "microphone=(), "
                    "geolocation=()"
                )

                headers[
                    "X-Permitted-Cross-Domain-Policies"
                ] = "none"

                # =========================================
                # AUTHENTICATION CACHE BOUNDARY
                # =========================================
                #
                # Every response under /api/v1/auth must be
                # treated as authentication-sensitive.
                #
                # This includes:
                #
                #   2xx success responses
                #   4xx credential failures
                #   CSRF failures
                #   throttle responses
                #   FastAPI 422 validation failures
                #   middleware-generated rejections
                #
                # Individual routes may still set these
                # headers during this migration. This
                # middleware intentionally normalizes them
                # to one authoritative value.

                if auth_response:
                    headers[
                        "Cache-Control"
                    ] = (
                        AUTH_CACHE_CONTROL
                    )

                    headers[
                        "Pragma"
                    ] = "no-cache"

                # =========================================
                # PRODUCTION TRANSPORT SECURITY
                # =========================================

                if (
                    settings
                    .is_production
                ):
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

    @staticmethod
    def _is_auth_path(
        path: str,
    ) -> bool:
        """
        Return True only for the actual authentication
        route boundary.

        Avoid a broad startswith('/api/v1/auth') check,
        because that would also match unrelated paths such
        as:

            /api/v1/authentication
            /api/v1/author
        """

        auth_prefix = (
            f"{settings.api_v1_prefix.rstrip('/')}"
            "/auth"
        )

        return (
            path == auth_prefix
            or path.startswith(
                f"{auth_prefix}/"
            )
        )