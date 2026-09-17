from functools import (
    lru_cache,
)
from pathlib import (
    Path,
)
from typing import (
    Annotated,
    Self,
)

from pydantic import (
    Field,
    StringConstraints,
    model_validator,
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

OPSFLOW_SECRETS_DIR = (
    INCIDENT_SERVICE_DIR
    .parent
    / ".opsflow-secrets"
)

DEFAULT_SERVICE_IDENTITY_PUBLIC_KEY_FILE = (
    OPSFLOW_SECRETS_DIR
    / "core-service-identity-public.pem"
)

DEFAULT_SERVICE_IDENTITY_SIGNING_PRIVATE_KEY_FILE = (
    OPSFLOW_SECRETS_DIR
    / "incident-service-identity-private.pem"
)

NonEmptyText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


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

    # Exposes process-local Prometheus metrics at /metrics.
    # The Incident Service remains private in Compose.

    metrics_enabled: bool = True

    database_url: str

    core_backend_url: str

    service_catalog_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=30,
    )

    # Core Backend service-identity verification contract.

    service_identity_issuer: NonEmptyText = (
        "opsflow-core-backend"
    )

    service_identity_audience: NonEmptyText = (
        "opsflow-incident-service"
    )

    service_identity_key_id: NonEmptyText = (
        "core-backend-key-1"
    )

    service_identity_public_key_file: Path = (
        DEFAULT_SERVICE_IDENTITY_PUBLIC_KEY_FILE
    )

    service_identity_previous_key_id: (
        NonEmptyText | None
    ) = None

    service_identity_previous_public_key_file: (
        Path | None
    ) = None

    service_identity_clock_skew_seconds: int = Field(
        default=5,
        ge=0,
        le=30,
    )

    # Incident Service outbound signing identity. These
    # settings are separate from the inbound Core Backend
    # verification settings above.

    service_identity_signing_private_key_path: Path = (
        DEFAULT_SERVICE_IDENTITY_SIGNING_PRIVATE_KEY_FILE
    )

    service_identity_signing_key_id: NonEmptyText = (
        "incident-service-key-1"
    )

    service_identity_signing_issuer: NonEmptyText = (
        "opsflow-incident-service"
    )

    service_identity_signing_token_ttl_seconds: int = Field(
        default=60,
        ge=30,
        le=120,
    )

    core_backend_audience: NonEmptyText = (
        "opsflow-core-backend"
    )

    model_config = SettingsConfigDict(
        env_file=INCIDENT_SERVICE_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(
        mode="after",
    )
    def validate_previous_verification_key(
        self,
    ) -> Self:
        previous_key_id_is_set = (
            self.service_identity_previous_key_id
            is not None
        )

        previous_key_file_is_set = (
            self
            .service_identity_previous_public_key_file
            is not None
        )

        if (
            previous_key_id_is_set
            != previous_key_file_is_set
        ):
            raise ValueError(
                "Previous service-identity key ID and "
                "public-key file must be configured "
                "together."
            )

        return self


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
