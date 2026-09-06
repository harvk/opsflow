from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


UNSAFE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


class BrowserTrustBoundaryMiddleware(BaseHTTPMiddleware):
    """
    Reject obviously untrusted browser-originated state-changing requests.

    This middleware is defense in depth. It does not replace CSRF-token
    validation on cookie-authenticated endpoints.
    """

    def __init__(
        self,
        app,
        *,
        allowed_origins: Iterable[str],
    ) -> None:
        super().__init__(app)

        self.allowed_origins = {
            origin.rstrip("/")
            for origin in allowed_origins
        }

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        fetch_site = request.headers.get("sec-fetch-site")

        # Modern browsers tell us explicitly when a request came
        # from a completely different site.
        if fetch_site == "cross-site":
            return self._forbidden(
                "Cross-site state-changing request rejected."
            )

        origin = request.headers.get("origin")

        if origin is not None:
            if not self._origin_is_allowed(
                request=request,
                origin=origin,
            ):
                return self._forbidden(
                    "Request origin is not trusted."
                )

            return await call_next(request)

        # Origin may not be present in every environment/browser.
        # Referer becomes the defense-in-depth fallback.
        referer = request.headers.get("referer")

        if referer is not None:
            referer_origin = self._extract_origin(referer)

            if (
                referer_origin is None
                or not self._origin_is_allowed(
                    request=request,
                    origin=referer_origin,
                )
            ):
                return self._forbidden(
                    "Request referer is not trusted."
                )

        # Missing browser headers are not automatically rejected here.
        #
        # Why?
        # Non-browser API clients such as pytest, curl, backend jobs,
        # and service-to-service clients do not necessarily send them.
        #
        # Cookie-authenticated endpoints will still require the actual
        # CSRF token in Phase 6.3B.
        return await call_next(request)

    def _origin_is_allowed(
        self,
        *,
        request: Request,
        origin: str,
    ) -> bool:
        normalized_origin = origin.rstrip("/")

        if normalized_origin in self.allowed_origins:
            return True

        # Also permit genuine same-origin requests, such as FastAPI
        # Swagger/OpenAPI requests served directly from the API host.
        request_origin = (
            f"{request.url.scheme}://{request.url.netloc}"
        )

        return normalized_origin == request_origin.rstrip("/")

    @staticmethod
    def _extract_origin(referer: str) -> str | None:
        parsed = urlsplit(referer)

        if not parsed.scheme or not parsed.netloc:
            return None

        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _forbidden(message: str) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "detail": message,
            },
        )