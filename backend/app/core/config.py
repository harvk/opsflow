from functools import (
    lru_cache,
)
from pathlib import (
    Path,
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

# =========================================================
# BACKEND CONFIGURATION PATH
# =========================================================
#
# This file lives at:
#
#     backend/app/core/config.py
#
# parents[0] -> backend/app/core
# parents[1] -> backend/app
# parents[2] -> backend
#
# Resolving the environment file from this module prevents
# configuration loading from depending on the shell's
# current working directory.
#
# In Docker the real .env file is deliberately absent from
# the image. Docker Compose injects the required application
# environment variables directly into the backend process.
#
# =========================================================

BACKEND_DIR = (
    Path(__file__)
    .resolve()
    .parents[2]
)

BACKEND_ENV_FILE = (
    BACKEND_DIR
    / ".env"
)

OPSFLOW_SECRETS_DIR = (
    BACKEND_DIR
    .parent
    / ".opsflow-secrets"
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

    # Exposes process-local Prometheus metrics at /metrics.
    #
    # The Docker Backend port remains bound to 127.0.0.1 in
    # local development.

    metrics_enabled: bool = True

    # =====================================================
    # DATABASE SETTINGS
    # =====================================================

    database_url: str

    # Optional for the production app; tests still supply it explicitly.
    test_database_url: str = ""

    # =====================================================
    # SERVICE-TO-SERVICE AUTHENTICATION
    # =====================================================

    service_identity_private_key_path: Path = Field(
        default=(
            BACKEND_DIR
            / "secrets"
            / "core-service-identity-private.pem"
        ),
    )

    service_identity_key_id: str = Field(
        default="core-backend-key-1",
        min_length=1,
        max_length=128,
    )

    service_identity_issuer: Literal[
        "opsflow-core-backend"
    ] = "opsflow-core-backend"

    service_identity_token_ttl_seconds: int = Field(
        default=60,
        ge=30,
        le=120,
    )

    incident_service_audience: Literal[
        "opsflow-incident-service"
    ] = "opsflow-incident-service"

    # Incident Service inbound verification contract. These
    # settings are separate from Core's outbound signing
    # identity above.

    incident_service_identity_issuer: Literal[
        "opsflow-incident-service"
    ] = "opsflow-incident-service"

    core_backend_service_audience: Literal[
        "opsflow-core-backend"
    ] = "opsflow-core-backend"

    incident_service_identity_key_id: str = Field(
        default="incident-service-key-1",
        min_length=1,
        max_length=128,
    )

    incident_service_identity_public_key_path: Path = Field(
        default=(
            OPSFLOW_SECRETS_DIR
            / "incident-service-identity-public.pem"
        ),
    )

    incident_service_identity_clock_skew_seconds: int = Field(
        default=5,
        ge=0,
        le=30,
    )

    # =====================================================
    # INCIDENT GATEWAY
    # =====================================================
    #
    # local:
    #     Core Backend executes Incident Management through
    #     the existing in-process LocalIncidentGateway.
    #
    # http:
    #     Core Backend delegates Incident Management to the
    #     independent Incident Service over HTTP.
    #
    # Read retries apply only to safe HTTP methods. Incident
    # mutations are never automatically retried.
    #
    # =====================================================

    incident_gateway_mode: Literal[
        "local",
        "http",
    ] = "local"

    incident_service_url: str = Field(
        default=(
            "http://incident-service:8000"
            "/api/v1"
        ),
        min_length=1,
        max_length=2048,
    )

    incident_service_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=30,
    )

    # Number of consecutive failed logical gateway
    # operations required to open the process-local circuit.
    #
    # A read that exhausts multiple retry attempts counts as
    # one failed operation.

    incident_service_circuit_failure_threshold: int = Field(
        default=3,
        ge=1,
        le=20,
    )

    # Time the circuit remains open before allowing one
    # half-open probe request.

    incident_service_circuit_recovery_seconds: float = Field(
        default=15.0,
        gt=0,
        le=300,
    )

    # Total attempts, including the initial request.
    #
    # A value of:
    #
    #     1 -> no retries
    #     2 -> one retry
    #     3 -> two retries
    #
    # The upper bound prevents configuration mistakes from
    # creating an excessive retry storm.

    incident_service_read_max_attempts: int = Field(
        default=2,
        ge=1,
        le=3,
    )

    # Initial exponential-backoff delay.
    #
    # With three attempts and a 0.1-second initial delay, the
    # delays would be:
    #
    #     after attempt 1 -> 0.1 seconds
    #     after attempt 2 -> 0.2 seconds

    incident_service_read_backoff_seconds: float = Field(
        default=0.1,
        ge=0,
        le=1,
    )

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

    access_token_expire_minutes: int = Field(
        default=15,
        ge=5,
        le=60,
    )

    refresh_token_expire_days: int = Field(
        default=7,
        ge=1,
        le=30,
    )

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
    # PASSWORD-RESET ABUSE PROTECTION
    # =====================================================

    password_reset_ip_max_requests: int = Field(
        default=10,
        ge=1,
        le=1000,
    )

    password_reset_ip_window_seconds: int = Field(
        default=900,
        ge=1,
        le=86400,
    )

    password_reset_account_max_requests: int = Field(
        default=3,
        ge=1,
        le=100,
    )

    password_reset_account_window_seconds: int = Field(
        default=3600,
        ge=1,
        le=86400,
    )

    # =====================================================
    # PASSWORD RESET DELIVERY
    # =====================================================

    password_reset_url: str = Field(
        default=(
            "http://localhost:5173/"
            "reset-password"
        ),
        min_length=1,
        max_length=2048,
    )

    # =====================================================
    # AWS INTEGRATIONS
    # =====================================================

    aws_region: str = Field(
        default="us-east-1",
        min_length=1,
        max_length=64,
    )

    # =====================================================
    # AWS SQS TASK PUBLICATION
    # =====================================================
    #
    # The queue URL is deployment-specific configuration.
    #
    # It remains optional at the global Settings level so
    # tooling and application paths that do not use task
    # publication can still construct Settings safely.
    #
    # get_task_publisher() enforces its presence when the
    # asynchronous publication capability is requested.
    #
    # Docker Compose additionally requires TASK_QUEUE_URL
    # for the backend runtime.
    #
    # =====================================================

    task_queue_url: (
        str | None
    ) = Field(
        default=None,
        min_length=1,
        max_length=2048,
    )

    # =====================================================
    # AWS SES PASSWORD RESET DELIVERY
    # =====================================================

    ses_from_email: str = Field(
        default=(
            "no-reply@example.com"
        ),
        min_length=3,
        max_length=320,
    )

    ses_configuration_set_name: (
        str | None
    ) = None

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
            env_file=(
                BACKEND_ENV_FILE
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
    return Settings()  # pyright: ignore[reportCallIssue]


settings = (
    get_settings()
)
