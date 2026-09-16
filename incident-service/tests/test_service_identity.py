from __future__ import annotations

from dataclasses import (
    dataclass,
)
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import (
    Any,
)
from uuid import (
    UUID,
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

from app.core.service_identity import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    JwtServiceTokenVerifier,
    ServiceAuthenticationError,
    ServiceIdentityConfigurationError,
    ServiceScope,
)

CORE_ISSUER = "opsflow-core-backend"
INCIDENT_AUDIENCE = "opsflow-incident-service"
CURRENT_KEY_ID = "core-backend-key-1"
PREVIOUS_KEY_ID = "core-backend-key-0"

TOKEN_ID = UUID(
    "11111111-1111-4111-8111-111111111111"
)

FIXED_NOW = datetime(
    2026,
    9,
    16,
    12,
    0,
    0,
    tzinfo=UTC,
)


@dataclass(
    frozen=True,
    slots=True,
)
class RsaKeyPair:
    private_key_pem: str
    public_key_pem: str


def generate_rsa_key_pair(
    *,
    key_size: int = 2048,
) -> RsaKeyPair:
    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
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

    return RsaKeyPair(
        private_key_pem=(
            private_key_pem
        ),
        public_key_pem=(
            public_key_pem
        ),
    )


@pytest.fixture
def current_key_pair(
) -> RsaKeyPair:
    return generate_rsa_key_pair()


@pytest.fixture
def previous_key_pair(
) -> RsaKeyPair:
    return generate_rsa_key_pair()


def build_payload(
    **overrides: Any,
) -> dict[
    str,
    Any,
]:
    issued_at = int(
        FIXED_NOW.timestamp()
    )

    payload: dict[
        str,
        Any,
    ] = {
        "iss": CORE_ISSUER,
        "sub": CORE_ISSUER,
        "aud": INCIDENT_AUDIENCE,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": (
            issued_at
            + 60
        ),
        "jti": str(
            TOKEN_ID
        ),
        "token_use": "service",
        "scope": "incidents:read",
    }

    payload.update(
        overrides
    )

    return payload


def create_token(
    key_pair: RsaKeyPair,
    *,
    key_id: str = CURRENT_KEY_ID,
    algorithm: str = "RS256",
    token_type: str = "JWT",
    payload: (
        dict[str, Any]
        | None
    ) = None,
) -> str:
    signing_key: str | bytes = (
        key_pair.private_key_pem
        if algorithm == "RS256"
        else b"test-hmac-secret"
    )

    return jwt.encode(
        (
            build_payload()
            if payload is None
            else payload
        ),
        signing_key,
        algorithm=algorithm,
        headers={
            "kid": key_id,
            "typ": token_type,
        },
    )


def build_verifier(
    current_key_pair: RsaKeyPair,
    *,
    additional_keys: (
        dict[str, str]
        | None
    ) = None,
    clock: Any = None,
    clock_skew_seconds: int = 5,
) -> JwtServiceTokenVerifier:
    public_keys = {
        CURRENT_KEY_ID: (
            current_key_pair
            .public_key_pem
        ),
    }

    if additional_keys is not None:
        public_keys.update(
            additional_keys
        )

    verifier_arguments: dict[
        str,
        Any,
    ] = {
        "public_keys": public_keys,
        "expected_issuer": (
            CORE_ISSUER
        ),
        "expected_audience": (
            INCIDENT_AUDIENCE
        ),
        "clock_skew_seconds": (
            clock_skew_seconds
        ),
    }

    if clock is not None:
        verifier_arguments[
            "clock"
        ] = clock

    return JwtServiceTokenVerifier(
        **verifier_arguments
    )


def assert_invalid_token(
    verifier: JwtServiceTokenVerifier,
    token: str,
) -> None:
    with pytest.raises(
        ServiceAuthenticationError,
        match=(
            INVALID_SERVICE_CREDENTIALS_MESSAGE
        ),
    ):
        verifier.verify_token(
            token
        )


def test_verifier_returns_expected_service_principal(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            scope=(
                "incidents:write incidents:read"
            )
        ),
    )

    principal = verifier.verify_token(
        token
    )

    assert principal.issuer == CORE_ISSUER
    assert principal.subject == CORE_ISSUER
    assert principal.audience == (
        INCIDENT_AUDIENCE
    )
    assert principal.token_id == TOKEN_ID
    assert principal.issued_at == FIXED_NOW
    assert principal.not_before == FIXED_NOW
    assert principal.expires_at == (
        FIXED_NOW
        + timedelta(
            seconds=60
        )
    )
    assert principal.scopes == frozenset(
        {
            ServiceScope.INCIDENTS_READ,
            ServiceScope.INCIDENTS_WRITE,
        }
    )


def test_verifier_accepts_previous_rotation_key(
    current_key_pair: RsaKeyPair,
    previous_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        additional_keys={
            PREVIOUS_KEY_ID: (
                previous_key_pair
                .public_key_pem
            )
        },
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        previous_key_pair,
        key_id=PREVIOUS_KEY_ID,
    )

    principal = verifier.verify_token(
        token
    )

    assert principal.token_id == TOKEN_ID


@pytest.mark.parametrize(
    "token",
    [
        "",
        "   ",
        "not-a-jwt",
    ],
)
def test_verifier_rejects_malformed_credentials(
    current_key_pair: RsaKeyPair,
    token: str,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_unknown_key_id(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        current_key_pair,
        key_id="unknown-key",
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_wrong_signature(
    current_key_pair: RsaKeyPair,
    previous_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        previous_key_pair,
        key_id=CURRENT_KEY_ID,
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_algorithm_confusion(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        current_key_pair,
        algorithm="HS256",
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_wrong_token_type(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        current_key_pair,
        token_type="USER",
    )

    assert_invalid_token(
        verifier,
        token,
    )


@pytest.mark.parametrize(
    (
        "claim_name",
        "claim_value",
    ),
    [
        (
            "iss",
            "untrusted-service",
        ),
        (
            "sub",
            "untrusted-service",
        ),
        (
            "aud",
            "wrong-audience",
        ),
        (
            "token_use",
            "access",
        ),
        (
            "jti",
            "not-a-uuid",
        ),
        (
            "scope",
            "incidents:delete",
        ),
        (
            "scope",
            "",
        ),
        (
            "scope",
            "incidents:read incidents:read",
        ),
    ],
)
def test_verifier_rejects_invalid_claim_values(
    current_key_pair: RsaKeyPair,
    claim_name: str,
    claim_value: str,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            **{
                claim_name: claim_value
            }
        ),
    )

    assert_invalid_token(
        verifier,
        token,
    )


@pytest.mark.parametrize(
    "claim_name",
    [
        "iss",
        "sub",
        "aud",
        "iat",
        "nbf",
        "exp",
        "jti",
        "token_use",
        "scope",
    ],
)
def test_verifier_rejects_missing_required_claims(
    current_key_pair: RsaKeyPair,
    claim_name: str,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    payload = build_payload()

    del payload[
        claim_name
    ]

    token = create_token(
        current_key_pair,
        payload=payload,
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_future_token(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    issued_at = int(
        (
            FIXED_NOW
            + timedelta(
                seconds=6
            )
        )
        .timestamp()
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            iat=issued_at,
            nbf=issued_at,
            exp=(
                issued_at
                + 60
            ),
        ),
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_accepts_token_within_clock_skew(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    issued_at = int(
        (
            FIXED_NOW
            + timedelta(
                seconds=5
            )
        )
        .timestamp()
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            iat=issued_at,
            nbf=issued_at,
            exp=(
                issued_at
                + 60
            ),
        ),
    )

    principal = verifier.verify_token(
        token
    )

    assert principal.issued_at == (
        FIXED_NOW
        + timedelta(
            seconds=5
        )
    )


def test_verifier_rejects_expired_token(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    issued_at = int(
        (
            FIXED_NOW
            - timedelta(
                seconds=66
            )
        )
        .timestamp()
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            iat=issued_at,
            nbf=issued_at,
            exp=(
                issued_at
                + 60
            ),
        ),
    )

    assert_invalid_token(
        verifier,
        token,
    )


@pytest.mark.parametrize(
    "ttl_seconds",
    [
        29,
        121,
    ],
)
def test_verifier_rejects_ttl_outside_contract(
    current_key_pair: RsaKeyPair,
    ttl_seconds: int,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    issued_at = int(
        FIXED_NOW.timestamp()
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            exp=(
                issued_at
                + ttl_seconds
            )
        ),
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_mismatched_not_before(
    current_key_pair: RsaKeyPair,
) -> None:
    verifier = build_verifier(
        current_key_pair,
        clock=lambda: FIXED_NOW,
    )

    issued_at = int(
        FIXED_NOW.timestamp()
    )

    token = create_token(
        current_key_pair,
        payload=build_payload(
            nbf=(
                issued_at
                + 1
            )
        ),
    )

    assert_invalid_token(
        verifier,
        token,
    )


def test_verifier_rejects_naive_clock(
    current_key_pair: RsaKeyPair,
) -> None:
    naive_now = (
        FIXED_NOW.replace(
            tzinfo=None
        )
    )

    verifier = build_verifier(
        current_key_pair,
        clock=lambda: naive_now,
    )

    token = create_token(
        current_key_pair
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "timezone-aware"
        ),
    ):
        verifier.verify_token(
            token
        )


@pytest.mark.parametrize(
    "clock_skew_seconds",
    [
        -1,
        31,
        True,
    ],
)
def test_verifier_rejects_invalid_clock_skew(
    current_key_pair: RsaKeyPair,
    clock_skew_seconds: Any,
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "clock_skew_seconds"
        ),
    ):
        build_verifier(
            current_key_pair,
            clock_skew_seconds=(
                clock_skew_seconds
            ),
        )


def test_verifier_requires_at_least_one_key(
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "At least one"
        ),
    ):
        JwtServiceTokenVerifier(
            public_keys={},
            expected_issuer=(
                CORE_ISSUER
            ),
            expected_audience=(
                INCIDENT_AUDIENCE
            ),
        )


def test_verifier_allows_at_most_two_keys(
    current_key_pair: RsaKeyPair,
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "At most two"
        ),
    ):
        JwtServiceTokenVerifier(
            public_keys={
                "key-1": (
                    current_key_pair
                    .public_key_pem
                ),
                "key-2": (
                    current_key_pair
                    .public_key_pem
                ),
                "key-3": (
                    current_key_pair
                    .public_key_pem
                ),
            },
            expected_issuer=(
                CORE_ISSUER
            ),
            expected_audience=(
                INCIDENT_AUDIENCE
            ),
        )


def test_verifier_rejects_invalid_public_key_pem(
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "valid PEM public key"
        ),
    ):
        JwtServiceTokenVerifier(
            public_keys={
                CURRENT_KEY_ID: (
                    "not-a-public-key"
                )
            },
            expected_issuer=(
                CORE_ISSUER
            ),
            expected_audience=(
                INCIDENT_AUDIENCE
            ),
        )


def test_verifier_rejects_undersized_rsa_key(
) -> None:
    undersized_key_pair = (
        generate_rsa_key_pair(
            key_size=1024
        )
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "at least 2048 bits"
        ),
    ):
        JwtServiceTokenVerifier(
            public_keys={
                CURRENT_KEY_ID: (
                    undersized_key_pair
                    .public_key_pem
                )
            },
            expected_issuer=(
                CORE_ISSUER
            ),
            expected_audience=(
                INCIDENT_AUDIENCE
            ),
        )