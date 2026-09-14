from fastapi import (
    FastAPI,
    Request,
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
from app.core.password_reset_messages import (
    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE,
)
from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
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
    # BROWSER TRUST BOUNDARY
    # =====================================================
    #
    # Starlette constructs user middleware in reverse
    # registration order.
    #
    # This middleware is registered first so CORS and the
    # response-security boundary can sit outside it.

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
    #
    # Starlette reverses middleware registration order.
    #
    # Security headers remain outside CORS and the browser
    # trust boundary. Request correlation is registered after
    # this middleware and becomes the final outer boundary.
    #
    # Security headers are therefore still applied to:
    #
    #     normal route responses
    #     FastAPI exception responses
    #     password-reset delivery failure responses
    #     browser-trust rejections
    #     CORS preflight responses

    application.add_middleware(
        SecurityHeadersMiddleware,
    )
    
    # =====================================================
    # REQUEST CORRELATION BOUNDARY
    # =====================================================
    #
    # Starlette reverses middleware registration order.
    #
    # Registering request correlation last makes it the
    # outermost user middleware. This ensures X-Request-ID is
    # attached even when a response originates from another
    # middleware rather than from a route.

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