from functools import (
    lru_cache,
)
from pathlib import (
    Path,
)

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

# =========================================================
# INCIDENT SERVICE CONFIGURATION PATH
# =========================================================

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
    Process-local settings for the OpsFlow Incident Service.

    The initial scaffold contains only application identity
    and routing settings. Database, Core Backend, and
    service-authentication settings will be introduced in the
    subphases that implement those capabilities.
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

    model_config = (
        SettingsConfigDict(
            env_file=(
                INCIDENT_SERVICE_ENV_FILE
            ),
            env_file_encoding=(
                "utf-8"
            ),
            case_sensitive=False,
            extra="ignore",
        )
    )


@lru_cache
def get_settings(
) -> Settings:
    return Settings()


settings = (
    get_settings()
)