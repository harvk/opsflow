from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    # ---------------------------------------------------------
    # Application settings
    # ---------------------------------------------------------

    app_name: str = "OpsFlow API"

    app_env: str = "development"

    api_v1_prefix: str = "/api/v1"

    frontend_origin: str = (
        "http://localhost:5173"
    )

    # ---------------------------------------------------------
    # Database settings
    # ---------------------------------------------------------

    database_url: str

    test_database_url: str

    # ---------------------------------------------------------
    # JWT authentication settings
    # ---------------------------------------------------------

    # Access-token signing key.
    jwt_secret_key: SecretStr

    # Refresh tokens deliberately use a different key.
    jwt_refresh_secret_key: SecretStr

    # Constrain the application to the algorithm
    # that this implementation is designed to use.
    jwt_algorithm: Literal["HS256"] = "HS256"

    jwt_issuer: str = "opsflow-api"

    jwt_audience: str = "opsflow-web"
    
    csrf_secret_key: str
    csrf_cookie_name: str = "opsflow_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # Short-lived bearer access credentials.
    access_token_expire_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
    )

    # Longer-lived credential used only to obtain
    # replacement access tokens.
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
    )

    # ---------------------------------------------------------
    # Refresh-cookie settings
    # ---------------------------------------------------------

    refresh_cookie_name: str = (
        "opsflow_refresh_token"
    )

    refresh_cookie_samesite: Literal[
        "lax",
        "strict",
        "none",
    ] = "lax"

    @property
    def is_production(self) -> bool:
        return (
            self.app_env.strip().lower()
            == "production"
        )

    @property
    def refresh_cookie_path(self) -> str:
        return (
            f"{self.api_v1_prefix}/auth"
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