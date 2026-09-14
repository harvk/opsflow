from functools import (
    lru_cache,
)
from pathlib import (
    Path,
)

from pydantic import (
    Field,
    SecretStr,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

INCIDENT_SERVICE_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

INCIDENT_SERVICE_ENV_FILE = (
    INCIDENT_SERVICE_DIR
    / ".env"
)


class Settings(
    BaseSettings
):
    """
    Process-local configuration for the Incident Service.

    TEST_DATABASE_URL is deliberately not an application
    setting. It is consumed only by test infrastructure and
    migration tooling.
    """

    app_name: str = (
        "OpsFlow Incident Service"
    )

    app_env: str = (
        "development"
    )

    api_v1_prefix: str = (
        "/api/v1"
    )

    database_url: str

    core_backend_url: str

    incident_service_token: SecretStr = Field(
        min_length=32,
    )

    service_catalog_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=30,
    )

    model_config = SettingsConfigDict(
        env_file=INCIDENT_SERVICE_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings(
) -> Settings:
    # BaseSettings supplies required values from configured
    # environment sources at runtime. Pylance cannot infer
    # those external settings sources.
    return Settings()  # pyright: ignore[reportCallIssue]


settings = (
    get_settings()
)