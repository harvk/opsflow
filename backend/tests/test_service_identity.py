from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from typing import (
    cast,
)
from uuid import (
    UUID,
)

import jwt
import pytest
from cryptography.hazmat.primitives import (
    serialization,
)
from cryptography.hazmat.primitives.asymmetric import (
    rsa,
)

from app.core.service_identity import (
    MAXIMUM_SERVICE_TOKEN_TTL_SECONDS,
    MINIMUM_SERVICE_TOKEN_TTL_SECONDS,
    JwtServiceTokenProvider,
    ServiceIdentityConfigurationError,
    ServiceScope,
    ServiceTokenCreationError,
)

CORE_IDENTITY = (
    "opsflow-core-backend"
)

INCIDENT_AUDIENCE = (
    "opsflow-incident-service"
)

KEY_ID = (
    "core-test-key-2026-09"
)

FIXED_TOKEN_ID = UUID(
    "4a491a92-b6c5-4fc1-a34f-435815c8d81f"
)


@pytest.fixture(
    scope="module"
)
def rsa_key_pair(
) -> tuple[
    str,
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
            encoding=(
                serialization
                .Encoding
                .PEM
            ),
            format=(
                serialization
                .PrivateFormat
                .PKCS8
            ),
            encryption_algorithm=(
                serialization
                .NoEncryption()
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
            encoding=(
                serialization
                .Encoding
                .PEM
            ),
            format=(
                serialization
                .PublicFormat
                .SubjectPublicKeyInfo
            ),
        )
        .decode(
            "utf-8"
        )
    )

    return (
        private_key_pem,
        public_key_pem,
    )


def build_provider(
    *,
    private_key_pem: str,
    issued_at: datetime,
    ttl_seconds: int = 60,
) -> JwtServiceTokenProvider:
    return (
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
            ttl_seconds=(
                ttl_seconds
            ),
            clock=lambda: issued_at,
            token_id_factory=(
                lambda: FIXED_TOKEN_ID
            ),
        )
    )


def test_provider_creates_expected_rs256_contract(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    (
        private_key_pem,
        public_key_pem,
    ) = rsa_key_pair

    issued_at = (
        datetime.now(
            UTC
        )
        .replace(
            microsecond=0
        )
    )

    provider = build_provider(
        private_key_pem=(
            private_key_pem
        ),
        issued_at=issued_at,
    )

    token = provider.create_token(
        audience=(
            INCIDENT_AUDIENCE
        ),
        scopes={
            ServiceScope
            .INCIDENTS_WRITE,
            ServiceScope
            .INCIDENTS_READ,
        },
    )

    header = (
        jwt.get_unverified_header(
            token
        )
    )

    assert header == {
        "alg": "RS256",
        "kid": KEY_ID,
        "typ": "JWT",
    }

    claims = jwt.decode(
        token,
        public_key_pem,
        algorithms=[
            "RS256"
        ],
        issuer=CORE_IDENTITY,
        audience=(
            INCIDENT_AUDIENCE
        ),
        options={
            "require": [
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
        },
    )

    assert claims[
        "iss"
    ] == CORE_IDENTITY

    assert claims[
        "sub"
    ] == CORE_IDENTITY

    assert claims[
        "aud"
    ] == INCIDENT_AUDIENCE

    assert claims[
        "iat"
    ] == int(
        issued_at.timestamp()
    )

    assert claims[
        "nbf"
    ] == int(
        issued_at.timestamp()
    )

    assert claims[
        "exp"
    ] == (
        int(
            issued_at.timestamp()
        )
        + 60
    )

    assert claims[
        "jti"
    ] == str(
        FIXED_TOKEN_ID
    )

    assert claims[
        "token_use"
    ] == "service"

    assert claims[
        "scope"
    ] == (
        "incidents:read "
        "incidents:write"
    )


def test_provider_creates_unique_default_token_ids(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    issued_at = (
        datetime.now(
            UTC
        )
        .replace(
            microsecond=0
        )
    )

    provider = (
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
            clock=lambda: issued_at,
        )
    )

    first_token = (
        provider.create_token(
            audience=(
                INCIDENT_AUDIENCE
            ),
            scopes={
                ServiceScope
                .INCIDENTS_READ
            },
        )
    )

    second_token = (
        provider.create_token(
            audience=(
                INCIDENT_AUDIENCE
            ),
            scopes={
                ServiceScope
                .INCIDENTS_READ
            },
        )
    )

    first_claims = jwt.decode(
        first_token,
        options={
            "verify_signature": False,
        },
    )

    second_claims = jwt.decode(
        second_token,
        options={
            "verify_signature": False,
        },
    )

    assert (
        first_claims[
            "jti"
        ]
        != second_claims[
            "jti"
        ]
    )


def test_provider_requires_at_least_one_scope(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    provider = build_provider(
        private_key_pem=(
            private_key_pem
        ),
        issued_at=(
            datetime.now(
                UTC
            )
        ),
    )

    with pytest.raises(
        ServiceTokenCreationError,
        match=(
            "At least one service scope"
        ),
    ):
        provider.create_token(
            audience=(
                INCIDENT_AUDIENCE
            ),
            scopes=set(),
        )


def test_provider_rejects_unregistered_scope_values(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    provider = build_provider(
        private_key_pem=(
            private_key_pem
        ),
        issued_at=(
            datetime.now(
                UTC
            )
        ),
    )

    invalid_scope = cast(
        ServiceScope,
        "incidents:delete",
    )

    with pytest.raises(
        ServiceTokenCreationError,
        match=(
            "Every service scope"
        ),
    ):
        provider.create_token(
            audience=(
                INCIDENT_AUDIENCE
            ),
            scopes={
                invalid_scope
            },
        )


@pytest.mark.parametrize(
    "ttl_seconds",
    [
        (
            MINIMUM_SERVICE_TOKEN_TTL_SECONDS
            - 1
        ),
        (
            MAXIMUM_SERVICE_TOKEN_TTL_SECONDS
            + 1
        ),
    ],
)
def test_provider_rejects_out_of_bounds_lifetime(
    rsa_key_pair: tuple[
        str,
        str,
    ],
    ttl_seconds: int,
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "ttl_seconds must be between"
        ),
    ):
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
            ttl_seconds=(
                ttl_seconds
            ),
        )


@pytest.mark.parametrize(
    (
        "key_id",
        "issuer",
    ),
    [
        (
            "",
            CORE_IDENTITY,
        ),
        (
            "   ",
            CORE_IDENTITY,
        ),
        (
            KEY_ID,
            "",
        ),
        (
            KEY_ID,
            "   ",
        ),
    ],
)
def test_provider_rejects_blank_identity_configuration(
    rsa_key_pair: tuple[
        str,
        str,
    ],
    key_id: str,
    issuer: str,
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "must not be empty"
        ),
    ):
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=key_id,
            issuer=issuer,
        )


def test_provider_rejects_blank_audience(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    provider = (
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
        )
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "audience must not be empty"
        ),
    ):
        provider.create_token(
            audience="   ",
            scopes={
                ServiceScope
                .INCIDENTS_READ
            },
        )


def test_provider_rejects_naive_clock(
    rsa_key_pair: tuple[
        str,
        str,
    ],
) -> None:
    private_key_pem, _ = (
        rsa_key_pair
    )

    provider = build_provider(
        private_key_pem=(
            private_key_pem
        ),
        issued_at=(
            datetime(
                2026,
                9,
                16,
                12,
                0,
                0,
                tzinfo=UTC,
            ).replace(
                tzinfo=None,
            )
        ),
    )

    with pytest.raises(
        ServiceTokenCreationError,
        match=(
            "timezone-aware datetime"
        ),
    ):
        provider.create_token(
            audience=(
                INCIDENT_AUDIENCE
            ),
            scopes={
                ServiceScope
                .INCIDENTS_READ
            },
        )


def test_provider_rejects_invalid_private_key(
) -> None:
    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "not a valid unencrypted PEM"
        ),
    ):
        JwtServiceTokenProvider(
            private_key_pem=(
                "not-a-private-key"
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
        )


def test_provider_rejects_small_rsa_key(
) -> None:
    private_key = (
        rsa.generate_private_key(
            public_exponent=65537,
            key_size=1024,
        )
    )

    private_key_pem = (
        private_key.private_bytes(
            encoding=(
                serialization
                .Encoding
                .PEM
            ),
            format=(
                serialization
                .PrivateFormat
                .PKCS8
            ),
            encryption_algorithm=(
                serialization
                .NoEncryption()
            ),
        )
        .decode(
            "utf-8"
        )
    )

    with pytest.raises(
        ServiceIdentityConfigurationError,
        match=(
            "at least 2048 bits"
        ),
    ):
        JwtServiceTokenProvider(
            private_key_pem=(
                private_key_pem
            ),
            key_id=KEY_ID,
            issuer=CORE_IDENTITY,
        )