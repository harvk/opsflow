from functools import (
    lru_cache,
)
from typing import (
    Literal,
)

from pydantic import (
    Field,
    SecretStr,
)

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(
    BaseSettings
):
    # =====================================================
    # APPLICATION SETTINGS
    # =====================================================

    app_name: str = (
        "OpsFlow API"
    )

    app_env: str = (
        "development"
    )

    api_v1_prefix: str = (
        "/api/v1"
    )

    frontend_origin: str = (
        "http://localhost:5173"
    )

    # =====================================================
    # DATABASE SETTINGS
    # =====================================================

    database_url: str

    test_database_url: str

    # =====================================================
    # JWT AUTHENTICATION SETTINGS
    # =====================================================

    # Short-lived bearer access-token signing key.
    jwt_secret_key: SecretStr

    # Refresh credentials deliberately use a separate key.
    jwt_refresh_secret_key: SecretStr

    # Sensitive-action reauthentication credentials use a
    # third independent key.
    jwt_reauth_secret_key: SecretStr

    jwt_algorithm: Literal[
        "HS256"
    ] = "HS256"

    jwt_issuer: str = (
        "opsflow-api"
    )

    jwt_audience: str = (
        "opsflow-web"
    )

    # =====================================================
    # CSRF SETTINGS
    # =====================================================

    csrf_secret_key: str

    csrf_cookie_name: str = (
        "opsflow_csrf"
    )

    csrf_header_name: str = (
        "X-CSRF-Token"
    )

    # =====================================================
    # TOKEN LIFETIMES
    # =====================================================

    # Ordinary bearer credential.
    access_token_expire_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
    )

    # Absolute persistent refresh-session lifetime.
    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
    )

    # Step-up authentication should remain very short-lived.
    #
    # Five minutes gives a user enough time to complete the
    # sensitive action without turning reauthentication into
    # another long-lived session credential.
    reauth_token_expire_minutes: int = Field(
        default=5,
        ge=1,
        le=15,
    )

    # =====================================================
    # LOGIN ABUSE PROTECTION
    # =====================================================

    auth_throttle_secret_key: SecretStr

    login_ip_max_attempts: int = Field(
        default=20,
        ge=5,
        le=500,
    )

    login_ip_window_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
    )

    login_account_max_failures: int = Field(
        default=8,
        ge=3,
        le=100,
    )

    login_account_window_seconds: int = Field(
        default=900,
        ge=60,
        le=86400,
    )

    # =====================================================
    # SECURITY EVENT LOGGING
    # =====================================================

    security_event_hmac_key: SecretStr

    # =====================================================
    # AUTHENTICATION-SESSION RETENTION
    # =====================================================

    auth_session_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
    )

    # =====================================================
    # REFRESH COOKIE SETTINGS
    # =====================================================

    refresh_cookie_name: str = (
        "opsflow_refresh_token"
    )

    refresh_cookie_samesite: Literal[
        "lax",
        "strict",
        "none",
    ] = "lax"

    @property
    def is_production(
        self,
    ) -> bool:
        return (
            self.app_env
            .strip()
            .lower()
            == "production"
        )

    @property
    def refresh_cookie_path(
        self,
    ) -> str:
        return (
            f"{self.api_v1_prefix}"
            "/auth"
        )

    # =====================================================
    # PYDANTIC SETTINGS CONFIGURATION
    # =====================================================

    model_config = (
        SettingsConfigDict(
            env_file=".env",
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
    return Settings()  # pyright: ignore[reportCallIssue]


settings = (
    get_settings()
)