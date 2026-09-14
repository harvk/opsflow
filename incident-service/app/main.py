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


def create_app(
    app_settings: Settings | None = None,
) -> FastAPI:
    """
    Construct the independently runnable Incident Service.

    Browser-facing CORS, CSRF, password-reset handlers, and
    Core Backend authentication middleware are deliberately
    absent from this service scaffold. They belong to the
    browser-facing Core Backend boundary.
    """

    configured_settings = (
        app_settings
        or settings
    )

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

    return application


app = (
    create_app()
)