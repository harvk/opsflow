from fastapi import (
    FastAPI,
    Request,
    status
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from fastapi.responses import (
    JSONResponse
)

from app.api.router import (
    api_router,
)

from app.core.config import (
    settings,
)

from app.middleware.broswer_trust import (
    BrowserTrustBoundaryMiddleware,
)

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
)

from app.core.logging_config import (
    configure_security_logging,
)

from app.core.auth_cookies import (
    prevent_auth_response_caching,
)

from app.core.password_reset_messages import (
    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE,
)

from app.services.password_reset_delivery import (
    PasswordResetDeliveryError,
)


configure_security_logging()


async def password_reset_delivery_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Preserve password-reset enumeration resistance when the
    delivery provider is unavailable.

    The PasswordResetDeliveryError has already escaped the
    route, allowing the request database transaction to roll
    back before this response is produced.

    No AWS/provider details or reset credential information
    are exposed.
    """

    response = (
        JSONResponse(
            status_code=(
                status.HTTP_202_ACCEPTED
            ),
            content={
                "message": (
                    PASSWORD_RESET_REQUEST_ACCEPTED_MESSAGE
                )
            },
        )
    )

    prevent_auth_response_caching(
        response
    )

    return response


# =========================================================
# APPLICATION FACTORY
# =========================================================


def create_app() -> FastAPI:
    """
    Construct the complete OpsFlow FastAPI application.

    The application factory is the single authoritative
    location for:

        application metadata
        middleware
        routing

    This prevents application instances created by tests,
    workers, or future tooling from receiving different
    security configuration.
    """

    application = FastAPI(
        title=(
            settings.app_name
        ),
        version=(
            "0.1.0"
        ),
        description=(
            "Backend API for the OpsFlow "
            "operations management platform."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    application.add_exception_handler(
        PasswordResetDeliveryError,
        password_reset_delivery_exception_handler,
    )

    # =====================================================
    # CORS
    # =====================================================
    #
    # Registered first.
    #
    # This is the innermost custom middleware layer.
    #
    # Credentialed browser authentication requires an
    # explicit trusted origin rather than "*".

    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            settings.frontend_origin,
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
            settings.csrf_header_name,
        ],
    )

    # =====================================================
    # BROWSER TRUST BOUNDARY
    # =====================================================
    #
    # Registered after CORS.
    #
    # This layer rejects hostile state-changing browser
    # traffic using:
    #
    #   Sec-Fetch-Site
    #   Origin
    #   Referer fallback
    #
    # It does not replace route-level CSRF validation.

    application.add_middleware(
        BrowserTrustBoundaryMiddleware,
        allowed_origins=[
            settings.frontend_origin,
        ],
    )

    # =====================================================
    # RESPONSE SECURITY HEADERS
    # =====================================================
    #
    # Registered last.
    #
    # Starlette's last-added user middleware becomes the
    # outermost user middleware layer.
    #
    # That is intentional:
    #
    # BrowserTrustBoundaryMiddleware may return its own 403
    # response without reaching CORS or an API route.
    #
    # SecurityHeadersMiddleware must sit outside it so those
    # responses still receive the baseline security policy.

    application.add_middleware(
        SecurityHeadersMiddleware,
    )

    # =====================================================
    # API ROUTES
    # =====================================================

    application.include_router(
        api_router,
        prefix=(
            settings.api_v1_prefix
        ),
    )

    return application


# =========================================================
# APPLICATION INSTANCE
# =========================================================


app = create_app()