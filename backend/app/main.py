from fastapi import (
    FastAPI,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import (
    CORSMiddleware,
)
from fastapi.responses import (
    JSONResponse,
)

from app.api.router import (
    api_router,
)
from app.core.config import (
    settings,
)
from app.core.logging_config import (
    configure_request_logging,
)
from app.core.metrics import (
    PROMETHEUS_CONTENT_TYPE,
    operational_metrics,
)
from app.core.password_reset_messages import (
    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE,
)
from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)
from app.middleware.metrics import (
    MetricsMiddleware,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)
from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)
from app.services.password_reset_delivery import (
    PasswordResetDeliveryError,
)

# =========================================================
# PASSWORD RESET DELIVERY FAILURE HANDLER
# =========================================================


async def password_reset_delivery_error_handler(
    _request: Request,
    _exc: Exception,
) -> JSONResponse:
    """
    Translate an internal password-reset delivery failure
    into the same public response returned for a normal
    password-reset request.

    This handler is registered specifically for
    PasswordResetDeliveryError, but the function accepts the
    base Exception type to satisfy FastAPI/Starlette's
    ExceptionHandler callable contract.

    No exception details are exposed to the caller.
    """

    return (
        JSONResponse(
            status_code=(
                status.HTTP_202_ACCEPTED
            ),
            content={
                "message": (
                    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE
                ),
            },
        )
    )


# =========================================================
# APPLICATION FACTORY
# =========================================================


def create_app(
) -> FastAPI:
    configure_request_logging()

    application = (
        FastAPI(
            title=(
                settings.app_name
            ),
            version="0.1.0",
            description=(
                "Backend API for the OpsFlow "
                "operations management platform."
            ),
            docs_url="/docs",
            redoc_url="/redoc",
        )
    )

    # =====================================================
    # APPLICATION EXCEPTION HANDLERS
    # =====================================================

    application.add_exception_handler(
        PasswordResetDeliveryError,
        password_reset_delivery_error_handler,
    )

    # =====================================================
    # API ROUTES
    # =====================================================

    application.include_router(
        api_router,
        prefix=(
            settings
            .api_v1_prefix
        ),
    )

    # =====================================================
    # PROMETHEUS METRICS
    # =====================================================
    #
    # The endpoint is deliberately excluded from OpenAPI.
    # It contains aggregate process metrics, never request
    # bodies, credentials, request IDs, or resource IDs.

    if settings.metrics_enabled:
        @application.get(
            "/metrics",
            include_in_schema=False,
        )
        def get_metrics(
        ) -> Response:
            return Response(
                content=(
                    operational_metrics
                    .render()
                ),
                headers={
                    "Content-Type": (
                        PROMETHEUS_CONTENT_TYPE
                    )
                },
            )

    # =====================================================
    # BROWSER TRUST BOUNDARY
    # =====================================================
    #
    # Starlette constructs user middleware in reverse
    # registration order.
    #
    # This middleware is registered first so CORS, security,
    # logging, and correlation can sit outside it.

    application.add_middleware(
        BrowserTrustBoundaryMiddleware,
        allowed_origins=[
            settings
            .frontend_origin
        ],
    )

    # =====================================================
    # CORS
    # =====================================================
    #
    # The frontend is allowed to read:
    #
    #     Retry-After
    #         password-reset throttling
    #
    #     X-Auth-Error-Code
    #         stable authentication error contract
    #
    #     X-Request-ID
    #         distributed request correlation

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings
            .frontend_origin
        ],
        allow_credentials=True,
        allow_methods=[
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-CSRF-Token",
            "X-Request-ID",
        ],
        expose_headers=[
            "Retry-After",
            "X-Auth-Error-Code",
            "X-Request-ID",
        ],
    )

    # =====================================================
    # RESPONSE SECURITY BOUNDARY
    # =====================================================

    application.add_middleware(
        SecurityHeadersMiddleware,
    )

    # =====================================================
    # STRUCTURED REQUEST LOGGING
    # =====================================================
    #
    # Request logging is registered after security headers,
    # placing it outside security, CORS, and browser trust.
    #
    # Metrics is registered after logging, and correlation is
    # registered last. Because Starlette reverses middleware
    # registration order, runtime order becomes:
    #
    #     correlation
    #     metrics
    #     request logging
    #     security headers
    #     CORS
    #     browser trust

    application.add_middleware(
        RequestLoggingMiddleware,
        service_name=(
            settings.app_name
        ),
        environment=(
            settings.app_env
        ),
    )

    # =====================================================
    # OPERATIONAL METRICS
    # =====================================================

    if settings.metrics_enabled:
        application.add_middleware(
            MetricsMiddleware,
            metrics=(
                operational_metrics
            ),
        )

    # =====================================================
    # REQUEST CORRELATION BOUNDARY
    # =====================================================
    #
    # Starlette reverses middleware registration order.
    #
    # Registering correlation last makes it the outermost
    # user middleware. The request ID is therefore bound
    # before metrics and structured request logging execute.

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    return application


# =========================================================
# APPLICATION INSTANCE
# =========================================================


app = (
    create_app()
)