from pathlib import (
    Path,
)

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import (
    rsa,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.core import (
    service_identity_provider,
)
from app.core.service_identity import (
    SERVICE_TOKEN_ALGORITHM,
    SERVICE_TOKEN_USE,
    ServiceIdentityConfigurationError,
    ServiceScope,
)

CORE_ISSUER = "opsflow-core-backend"
INCIDENT_AUDIENCE = "opsflow-incident-service"
KEY_ID = "core-backend-test-key"
TOKEN_TTL_SECONDS = 60


@pytest.fixture
def rsa_key_files(
    tmp_path: Path,
) -> tuple[
    Path,
    str,
]:
    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
    )

    private_key_pem = (
        private_key.private_bytes(
            encoding=Encoding.PEM,
            format=(
                PrivateFormat.PKCS8
            ),
            encryption_algorithm=(
                NoEncryption()
            ),
        )
        .decode(
            "utf-8"
        )
    )

    public_key_pem = (
        private_key
        .public_key()
        .public_bytes(
            encoding=Encoding.PEM,
            format=(
                PublicFormat.SubjectPublicKeyInfo
            ),
        )
        .decode(
            "utf-8"
        )
    )

    private_key_path = (
        tmp_path
        / "core-service-identity-private.pem"
    )

    private_key_path.write_text(
        private_key_pem,
        encoding="utf-8",
    )

    return (
        private_key_path,
        public_key_pem,
    )


def test_builder_loads_key_and_constructs_provider(
    rsa_key_files: tuple[
        Path,
        str,
    ],
) -> None:
    (
        private_key_path,
        public_key_pem,
    ) = rsa_key_files

    provider = (
        service_identity_provider
        .build_service_token_provider(
            private_key_path=(
                private_key_path
            ),
            key_id=KEY_ID,
            issuer=CORE_ISSUER,
            ttl_seconds=(
                TOKEN_TTL_SECONDS
            ),
        )
    )

    token = provider.create_token(
        audience=(
            INCIDENT_AUDIENCE
        ),
        scopes={
            ServiceScope.INCIDENTS_READ
        },
    )

    header = (
        jwt.get_unverified_header(
            token
        )
    )

    payload = jwt.decode(
        token,
        public_key_pem,
        algorithms=[
            SERVICE_TOKEN_ALGORITHM
        ],
        audience=(
            INCIDENT_AUDIENCE
        ),
        issuer=CORE_ISSUER,
    )

    assert header["alg"] == (
        SERVICE_TOKEN_ALGORITHM
    )
    assert header["kid"] == KEY_ID
    assert payload["iss"] == CORE_ISSUER
    assert payload["sub"] == CORE_ISSUER
    assert payload["aud"] == (
        INCIDENT_AUDIENCE
    )
    assert payload["token_use"] == (
        SERVICE_TOKEN_USE
    )
    assert payload["scope"] == (
        ServiceScope
        .INCIDENTS_READ
        .value
    )
    assert (
        payload["exp"]
        - payload["iat"]
    ) == TOKEN_TTL_SECONDS


def test_builder_rejects_missing_private_key_file(
    tmp_path: Path,
) -> None:
    missing_key_path = (
        tmp_path
        / "missing-private-key.pem"
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "private key could not be loaded"
        ),
    ):
        (
            service_identity_provider
            .build_service_token_provider(
                private_key_path=(
                    missing_key_path
                ),
                key_id=KEY_ID,
                issuer=CORE_ISSUER,
                ttl_seconds=(
                    TOKEN_TTL_SECONDS
                ),
            )
        )


def test_builder_rejects_non_utf8_private_key_file(
    tmp_path: Path,
) -> None:
    invalid_key_path = (
        tmp_path
        / "invalid-private-key.pem"
    )

    invalid_key_path.write_bytes(
        b"\xff\xfe\xfd"
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "private key could not be loaded"
        ),
    ):
        (
            service_identity_provider
            .build_service_token_provider(
                private_key_path=(
                    invalid_key_path
                ),
                key_id=KEY_ID,
                issuer=CORE_ISSUER,
                ttl_seconds=(
                    TOKEN_TTL_SECONDS
                ),
            )
        )


def test_configured_provider_is_cached(
    monkeypatch: pytest.MonkeyPatch,
    rsa_key_files: tuple[
        Path,
        str,
    ],
) -> None:
    (
        private_key_path,
        _public_key_pem,
    ) = rsa_key_files

    monkeypatch.setattr(
        service_identity_provider.settings,
        "service_identity_private_key_path",
        private_key_path,
    )
    monkeypatch.setattr(
        service_identity_provider.settings,
        "service_identity_key_id",
        KEY_ID,
    )
    monkeypatch.setattr(
        service_identity_provider.settings,
        "service_identity_issuer",
        CORE_ISSUER,
    )
    monkeypatch.setattr(
        service_identity_provider.settings,
        "service_identity_token_ttl_seconds",
        TOKEN_TTL_SECONDS,
    )

    (
        service_identity_provider
        .get_service_token_provider
        .cache_clear()
    )

    try:
        first_provider = (
            service_identity_provider
            .get_service_token_provider()
        )
        second_provider = (
            service_identity_provider
            .get_service_token_provider()
        )

        assert (
            first_provider
            is second_provider
        )

    finally:
        (
            service_identity_provider
            .get_service_token_provider
            .cache_clear()
        )