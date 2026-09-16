from pathlib import (
    Path,
)

from app.core.config import (
    Settings,
)
from app.core.service_identity import (
    JwtServiceTokenVerifier,
    ServiceIdentityConfigurationError,
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
    Load the current key and optional previous rotation key.

    The Settings model guarantees that the previous key ID
    and path are either both configured or both absent.
    """

    verification_keys = {
        app_settings.service_identity_key_id: (
            _read_public_key(
                app_settings
                .service_identity_public_key_file,
                setting_name=(
                    "SERVICE_IDENTITY_PUBLIC_KEY_FILE"
                ),
            )
        )
    }

    previous_key_id = (
        app_settings
        .service_identity_previous_key_id
    )

    previous_public_key_file = (
        app_settings
        .service_identity_previous_public_key_file
    )

    if (
        previous_key_id is not None
        and previous_public_key_file is not None
    ):
        if (
            previous_key_id
            == app_settings.service_identity_key_id
        ):
            raise ServiceIdentityConfigurationError(
                "Current and previous service-identity "
                "key IDs must be different."
            )

        verification_keys[
            previous_key_id
        ] = _read_public_key(
            previous_public_key_file,
            setting_name=(
                "SERVICE_IDENTITY_PREVIOUS_"
                "PUBLIC_KEY_FILE"
            ),
        )

    return verification_keys


def build_service_token_verifier(
    app_settings: Settings,
) -> JwtServiceTokenVerifier:
    """
    Construct the Incident Service's RS256 verifier.

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
            .service_identity_issuer
        ),
        expected_audience=(
            app_settings
            .service_identity_audience
        ),
        clock_skew_seconds=(
            app_settings
            .service_identity_clock_skew_seconds
        ),
    )