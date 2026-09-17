from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.core.service_identity import (
    SERVICE_TOKEN_ALGORITHM,
    SERVICE_TOKEN_USE,
    ServiceIdentityConfigurationError,
    ServiceScope,
)
from app.core.service_token_verifier import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    JwtServiceTokenVerifier,
    ServiceAuthenticationError,
    ServiceAuthenticationFailureReason,
)
from app.core.service_token_verifier_loader import (
    _read_public_key,
)

INCIDENT_ISSUER = "opsflow-incident-service"
CORE_AUDIENCE = "opsflow-core-backend"
KEY_ID = "incident-service-test-key"
ISSUED_AT = datetime(
    2026,
    9,
    16,
    12,
    0,
    tzinfo=UTC,
)


@pytest.fixture
def rsa_key_pair() -> tuple[str, str]:
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

    return private_key_pem, public_key_pem


def create_token(
    private_key_pem: str,
    *,
    audience: str = CORE_AUDIENCE,
    key_id: str = KEY_ID,
    scope: str = ServiceScope.SERVICES_READ.value,
) -> str:
    return jwt.encode(
        {
            "iss": INCIDENT_ISSUER,
            "sub": INCIDENT_ISSUER,
            "aud": audience,
            "iat": ISSUED_AT,
            "nbf": ISSUED_AT,
            "exp": ISSUED_AT + timedelta(seconds=60),
            "jti": str(uuid4()),
            "token_use": SERVICE_TOKEN_USE,
            "scope": scope,
        },
        private_key_pem,
        algorithm=SERVICE_TOKEN_ALGORITHM,
        headers={
            "typ": "JWT",
            "kid": key_id,
        },
    )


def build_verifier(
    public_key_pem: str,
) -> JwtServiceTokenVerifier:
    return JwtServiceTokenVerifier(
        public_keys={
            KEY_ID: public_key_pem
        },
        expected_issuer=INCIDENT_ISSUER,
        expected_audience=CORE_AUDIENCE,
        clock_skew_seconds=5,
        clock=lambda: ISSUED_AT,
    )


def test_verifier_accepts_services_read_token(
    rsa_key_pair: tuple[str, str],
) -> None:
    private_key_pem, public_key_pem = rsa_key_pair
    token = create_token(private_key_pem)

    principal = build_verifier(
        public_key_pem
    ).verify_token(token)

    assert principal.issuer == INCIDENT_ISSUER
    assert principal.subject == INCIDENT_ISSUER
    assert principal.audience == CORE_AUDIENCE
    assert principal.scopes == frozenset(
        {
            ServiceScope.SERVICES_READ
        }
    )


@pytest.mark.parametrize(
    (
        "audience",
        "key_id",
        "scope",
        "expected_reason",
    ),
    [
        (
            "wrong-audience",
            KEY_ID,
            ServiceScope.SERVICES_READ.value,
            ServiceAuthenticationFailureReason.INVALID_AUDIENCE,
        ),
        (
            CORE_AUDIENCE,
            "unknown-key",
            ServiceScope.SERVICES_READ.value,
            ServiceAuthenticationFailureReason.UNKNOWN_KEY,
        ),
        (
            CORE_AUDIENCE,
            KEY_ID,
            "services:delete",
            ServiceAuthenticationFailureReason.INVALID_SCOPE_CONTRACT,
        ),
    ],
)
def test_verifier_rejects_untrusted_token_contracts(
    rsa_key_pair: tuple[str, str],
    audience: str,
    key_id: str,
    scope: str,
    expected_reason: ServiceAuthenticationFailureReason,
) -> None:
    private_key_pem, public_key_pem = rsa_key_pair
    token = create_token(
        private_key_pem,
        audience=audience,
        key_id=key_id,
        scope=scope,
    )

    with pytest.raises(
        ServiceAuthenticationError,
        match=INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ) as exc_info:
        build_verifier(
            public_key_pem
        ).verify_token(token)

    assert exc_info.value.reason is expected_reason


def test_verifier_classifies_malformed_credential(
    rsa_key_pair: tuple[str, str],
) -> None:
    _, public_key_pem = rsa_key_pair

    with pytest.raises(
        ServiceAuthenticationError,
        match=INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ) as exc_info:
        build_verifier(
            public_key_pem
        ).verify_token("not-a-jwt")

    assert exc_info.value.reason is (
        ServiceAuthenticationFailureReason
        .MALFORMED_CREDENTIAL
    )


def test_public_key_loader_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match="PUBLIC_KEY_PATH could not be read",
    ):
        _read_public_key(
            tmp_path
            / "missing-public-key.pem",
            setting_name=(
                "INCIDENT_SERVICE_IDENTITY_"
                "PUBLIC_KEY_PATH"
            ),
        )
