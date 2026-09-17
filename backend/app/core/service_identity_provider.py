from __future__ import annotations

from functools import (
    lru_cache,
)
from pathlib import (
    Path,
)

from app.core.config import (
    settings,
)
from app.core.service_identity import (
    JwtServiceTokenProvider,
    ServiceIdentityConfigurationError,
    ServiceTokenProvider,
)


def build_service_token_provider(
    *,
    private_key_path: Path,
    key_id: str,
    issuer: str,
    ttl_seconds: int,
) -> ServiceTokenProvider:
    """
    Build a service-token provider from a PEM key file.

    Key-file loading is isolated from the JWT provider so
    the cryptographic component remains independently
    testable and does not own deployment-specific paths.
    """

    try:
        private_key_pem = (
            private_key_path
            .read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        UnicodeError,
    ) as exc:
        raise (
            ServiceIdentityConfigurationError(
                "The service-identity private key "
                "could not be loaded."
            )
        ) from exc

    return (
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=key_id,
            issuer=issuer,
            ttl_seconds=(
                ttl_seconds
            ),
        )
    )


@lru_cache(
    maxsize=1
)
def get_service_token_provider(
) -> ServiceTokenProvider:
    """
    Construct the process-wide Core service-token provider.

    The immutable RSA private key is parsed only once per
    Backend process. Individual outbound calls still receive
    independently created short-lived JWTs with unique IDs.
    """

    return (
        build_service_token_provider(
            private_key_path=(
                settings
                .service_identity_private_key_path
            ),
            key_id=(
                settings
                .service_identity_key_id
            ),
            issuer=(
                settings
                .service_identity_issuer
            ),
            ttl_seconds=(
                settings
                .service_identity_token_ttl_seconds
            ),
        )
    )