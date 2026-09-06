from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # Application settings
    # ---------------------------------------------------------
    app_name: str = "OpsFlow API"
    app_env: str = "development"

    api_v1_prefix: str = "/api/v1"

    frontend_origin: str = "http://localhost:5173"

    # ---------------------------------------------------------
    # Database settings
    # ---------------------------------------------------------
    database_url: str
    test_database_url: str

    # ---------------------------------------------------------
    # JWT authentication settings
    # ---------------------------------------------------------
    jwt_secret_key: SecretStr

    jwt_issuer: str = "opsflow-api"
    jwt_audience: str = "opsflow-web"

    access_token_expire_minutes: int = Field(
        default=30,
        ge=5,
        le=1440,
    )

    # ---------------------------------------------------------
    # Pydantic settings configuration
    # ---------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]


settings = get_settings()