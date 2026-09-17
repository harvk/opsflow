from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.core import service_token_provider
from app.core.service_identity import (
    SERVICE_TOKEN_ALGORITHM,
    SERVICE_TOKEN_USE,
    ServiceIdentityConfigurationError,
    ServiceScope,
)

INCIDENT_ISSUER = "opsflow-incident-service"
CORE_AUDIENCE = "opsflow-core-backend"
KEY_ID = "incident-service-test-key"
TOKEN_TTL_SECONDS = 60


@pytest.fixture
def rsa_key_files(
    tmp_path: Path,
) -> tuple[Path, str]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    private_key_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode("utf-8")

    public_key_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    private_key_path = (
        tmp_path
        / "incident-service-identity-private.pem"
    )
    private_key_path.write_text(
        private_key_pem,
        encoding="utf-8",
    )

    return private_key_path, public_key_pem


def test_builder_creates_services_read_token(
    rsa_key_files: tuple[Path, str],
) -> None:
    private_key_path, public_key_pem = rsa_key_files

    provider = (
        service_token_provider
        .build_service_token_provider(
            private_key_path=private_key_path,
            key_id=KEY_ID,
            issuer=INCIDENT_ISSUER,
            ttl_seconds=TOKEN_TTL_SECONDS,
        )
    )

    token = provider.create_token(
        audience=CORE_AUDIENCE,
        scopes={
            ServiceScope.SERVICES_READ
        },
    )

    header = jwt.get_unverified_header(token)
    payload = jwt.decode(
        token,
        public_key_pem,
        algorithms=[
            SERVICE_TOKEN_ALGORITHM
        ],
        audience=CORE_AUDIENCE,
        issuer=INCIDENT_ISSUER,
    )

    assert header["alg"] == SERVICE_TOKEN_ALGORITHM
    assert header["kid"] == KEY_ID
    assert payload["iss"] == INCIDENT_ISSUER
    assert payload["sub"] == INCIDENT_ISSUER
    assert payload["aud"] == CORE_AUDIENCE
    assert payload["token_use"] == SERVICE_TOKEN_USE
    assert payload["scope"] == (
        ServiceScope.SERVICES_READ.value
    )
    assert (
        payload["exp"]
        - payload["iat"]
    ) == TOKEN_TTL_SECONDS


def test_builder_rejects_missing_private_key(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match="private key could not be loaded",
    ):
        (
            service_token_provider
            .build_service_token_provider(
                private_key_path=(
                    tmp_path
                    / "missing-private-key.pem"
                ),
                key_id=KEY_ID,
                issuer=INCIDENT_ISSUER,
                ttl_seconds=TOKEN_TTL_SECONDS,
            )
        )


def test_builder_rejects_non_utf8_private_key(
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
        match="private key could not be loaded",
    ):
        (
            service_token_provider
            .build_service_token_provider(
                private_key_path=invalid_key_path,
                key_id=KEY_ID,
                issuer=INCIDENT_ISSUER,
                ttl_seconds=TOKEN_TTL_SECONDS,
            )
        )


def test_configured_provider_is_cached(
    monkeypatch: pytest.MonkeyPatch,
    rsa_key_files: tuple[Path, str],
) -> None:
    private_key_path, _public_key_pem = rsa_key_files
    settings = (
        service_token_provider
        .get_settings()
    )

    monkeypatch.setattr(
        settings,
        "service_identity_signing_private_key_path",
        private_key_path,
    )
    monkeypatch.setattr(
        settings,
        "service_identity_signing_key_id",
        KEY_ID,
    )
    monkeypatch.setattr(
        settings,
        "service_identity_signing_issuer",
        INCIDENT_ISSUER,
    )
    monkeypatch.setattr(
        settings,
        "service_identity_signing_token_ttl_seconds",
        TOKEN_TTL_SECONDS,
    )

    (
        service_token_provider
        .get_service_token_provider
        .cache_clear()
    )

    try:
        first_provider = (
            service_token_provider
            .get_service_token_provider()
        )
        second_provider = (
            service_token_provider
            .get_service_token_provider()
        )

        assert first_provider is second_provider

    finally:
        (
            service_token_provider
            .get_service_token_provider
            .cache_clear()
        )
