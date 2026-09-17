from functools import (
    lru_cache,
)

from fastapi import (
    FastAPI,
    Response,
)

from app.api.dependencies import (
    get_service_token_verifier,
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
from app.core.metrics import (
    PROMETHEUS_CONTENT_TYPE,
    operational_metrics,
)
from app.core.service_identity import (
    ServiceTokenVerifier,
)
from app.core.service_identity_loader import (
    build_service_token_verifier,
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

    if configured_settings.metrics_enabled:
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

    if app_settings is not None:
        application.dependency_overrides[
            get_settings
        ] = lambda: configured_settings

        @lru_cache(
            maxsize=1,
        )
        def get_application_service_token_verifier(
        ) -> ServiceTokenVerifier:
            return build_service_token_verifier(
                configured_settings
            )

        application.dependency_overrides[
            get_service_token_verifier
        ] = (
            get_application_service_token_verifier
        )

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

    if configured_settings.metrics_enabled:
        application.add_middleware(
            MetricsMiddleware,
            metrics=(
                operational_metrics
            ),
        )

    application.add_middleware(
        RequestCorrelationMiddleware,
    )

    return application


app = (
    create_app()
)