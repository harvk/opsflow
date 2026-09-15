from pydantic import (
    SecretStr,
)

from app.core.config import (
    Settings,
)
from app.main import (
    create_app,
)
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)


def build_test_settings(
) -> Settings:
    return Settings(
        app_name=(
            "OpsFlow Incident Service"
        ),
        app_env="test",
        api_v1_prefix="/api/v1",
        database_url=(
            "postgresql+psycopg://"
            "test:test@localhost/test"
        ),
        core_backend_url=(
            "http://core-backend.test/api/v1"
        ),
        incident_service_token=(
            SecretStr(
                "test-internal-token-that-is-"
                "at-least-32-characters"
            )
        ),
    )


def test_request_middleware_registration_and_order(
) -> None:
    application = create_app(
        build_test_settings()
    )

    assert len(
        application.user_middleware
    ) == 2

    assert (
        application
        .user_middleware[0]
        .cls
        is RequestCorrelationMiddleware
    )

    assert (
        application
        .user_middleware[1]
        .cls
        is RequestLoggingMiddleware
    )