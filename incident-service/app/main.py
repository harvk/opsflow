from fastapi import (
    FastAPI,
)

from app.api.router import (
    api_router,
)
from app.core.config import (
    Settings,
    get_settings,
    settings,
)
from app.core.logging_config import (
    configure_request_logging,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)


def create_app(
    app_settings: Settings | None = None,
) -> FastAPI:
    """
    Construct the independently runnable Incident Service.

    Browser-facing CORS, CSRF, password-reset handlers, and
    Core Backend authentication middleware are deliberately
    absent from this service. They belong to the public
    Backend boundary.
    """

    configured_settings = (
        app_settings
        or settings
    )

    configure_request_logging()

    application = (
        FastAPI(
            title=(
                configured_settings
                .app_name
            ),
            version="0.1.0",
            description=(
                "Incident Management service for the "
                "OpsFlow operations platform."
            ),
            docs_url="/docs",
            redoc_url="/redoc",
        )
    )

    application.include_router(
        api_router,
        prefix=(
            configured_settings
            .api_v1_prefix
        ),
    )

    if app_settings is not None:
        application.dependency_overrides[
            get_settings
        ] = lambda: configured_settings

    # Logging is added first and correlation is added last.
    # Because Starlette reverses registration order, the
    # request ID is bound before request logging begins.

    application.add_middleware(
        RequestLoggingMiddleware,
        service_name=(
            configured_settings
            .app_name
        ),
        environment=(
            configured_settings
            .app_env
        ),
    )

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    return application


app = (
    create_app()
)