from pathlib import (
    Path,
)

from app.core.config import (
    Settings,
)
from app.core.service_identity import (
    ServiceIdentityConfigurationError,
)
from app.core.service_token_verifier import (
    JwtServiceTokenVerifier,
)


def _read_public_key(
    public_key_file: Path,
    *,
    setting_name: str,
) -> str:
    """
    Read one configured verification key as UTF-8 text.

    Configuration failures intentionally identify the
    setting but do not disclose the configured filesystem
    path in the exception message.
    """

    try:
        public_key_pem = (
            public_key_file.read_text(
                encoding="utf-8",
            )
        )

    except (
        OSError,
        UnicodeError,
    ) as exc:
        raise ServiceIdentityConfigurationError(
            f"{setting_name} could not be read."
        ) from exc

    if not public_key_pem.strip():
        raise ServiceIdentityConfigurationError(
            f"{setting_name} must not be empty."
        )

    return public_key_pem


def load_service_verification_keys(
    app_settings: Settings,
) -> dict[
    str,
    str,
]:
    """
    Load the Incident Service's current public key.
    """

    verification_keys = {
        app_settings.incident_service_identity_key_id: (
            _read_public_key(
                app_settings
                .incident_service_identity_public_key_path,
                setting_name=(
                    "INCIDENT_SERVICE_IDENTITY_"
                    "PUBLIC_KEY_PATH"
                ),
            )
        )
    }

    return verification_keys


def build_service_token_verifier(
    app_settings: Settings,
) -> JwtServiceTokenVerifier:
    """
    Construct Core Backend's Incident Service verifier.

    Key parsing and RSA-strength validation remain owned by
    JwtServiceTokenVerifier so there is one cryptographic
    validation boundary.
    """

    return JwtServiceTokenVerifier(
        public_keys=(
            load_service_verification_keys(
                app_settings
            )
        ),
        expected_issuer=(
            app_settings
            .incident_service_identity_issuer
        ),
        expected_audience=(
            app_settings
            .core_backend_service_audience
        ),
        clock_skew_seconds=(
            app_settings
            .incident_service_identity_clock_skew_seconds
        ),
    )
