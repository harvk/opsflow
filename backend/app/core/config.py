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
    # Security event logging
    # ---------------------------------------------------------

    # Dedicated key used only to pseudonymize identifiers
    # written to security logs.
    #
    # Do not reuse JWT, refresh-token, CSRF, or login-throttle
    # secrets here.
    security_event_hmac_key: SecretStr
    
        # ---------------------------------------------------------
    # Login abuse protection
    # ---------------------------------------------------------

    # Dedicated secret used to pseudonymize throttle keys.
    #
    # This should remain separate from:
    #
    #   jwt_secret_key
    #   jwt_refresh_secret_key
    #   csrf_secret_key
    #
    # A separate key limits the blast radius if one
    # credential is ever exposed.
    auth_throttle_secret_key: SecretStr

    # Maximum number of authentication submissions allowed
    # from one source address during the IP window.
    login_ip_max_attempts: int = Field(
        default=20,
        ge=5,
        le=500,
    )

    # Length of the source-address sliding window.
    login_ip_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
    )

    # Maximum number of failed login attempts allowed against
    # one normalized account identifier.
    login_account_max_failures: int = Field(
        default=8,
        ge=3,
        le=100,
    )

    # How long failed account attempts remain in the
    # sliding-window history.
    login_account_window_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
    )

    # ---------------------------------------------------------
    # Security event logging
    # ---------------------------------------------------------

    # Dedicated HMAC key used to create stable pseudonymous
    # identifiers in security/audit logs.
    #
    # Raw user email addresses should not be written to
    # authentication-failure logs.
    security_event_hmac_key: SecretStr

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