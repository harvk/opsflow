from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import (
    Annotated,
    Any,
)
from uuid import (
    uuid4,
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
from fastapi import (
    Depends,
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

from app.api import (
    dependencies,
)
from app.core.service_identity import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    SERVICE_TOKEN_ALGORITHM,
    SERVICE_TOKEN_USE,
    JwtServiceTokenVerifier,
    ServiceAuthenticationError,
    ServiceAuthenticationFailureReason,
    ServicePrincipal,
    ServiceScope,
)

CORE_ISSUER = "opsflow-core-backend"
INCIDENT_AUDIENCE = "opsflow-incident-service"
CURRENT_KEY_ID = "core-backend-key-1"
FIXED_NOW = datetime(
    2026,
    9,
    17,
    12,
    0,
    tzinfo=UTC,
)


@pytest.fixture
def key_pairs(
) -> tuple[
    tuple[str, str],
    tuple[str, str],
]:
    def generate(
    ) -> tuple[str, str]:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        private_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.PKCS8,
            encryption_algorithm=NoEncryption(),
        ).decode(
            "utf-8"
        )

        public_pem = (
            private_key
            .public_key()
            .public_bytes(
                encoding=Encoding.PEM,
                format=PublicFormat.SubjectPublicKeyInfo,
            )
            .decode(
                "utf-8"
            )
        )

        return (
            private_pem,
            public_pem,
        )

    return (
        generate(),
        generate(),
    )


def build_payload(
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "iss": CORE_ISSUER,
        "sub": CORE_ISSUER,
        "aud": INCIDENT_AUDIENCE,
        "iat": FIXED_NOW,
        "nbf": FIXED_NOW,
        "exp": (
            FIXED_NOW
            + timedelta(
                seconds=60
            )
        ),
        "jti": str(
            uuid4()
        ),
        "token_use": SERVICE_TOKEN_USE,
        "scope": ServiceScope.INCIDENTS_READ.value,
    }
    payload.update(
        overrides
    )
    return payload


def create_token(
    private_key: str | bytes,
    *,
    payload: dict[str, Any] | None = None,
    algorithm: str = SERVICE_TOKEN_ALGORITHM,
    key_id: str | None = CURRENT_KEY_ID,
    token_type: str = "JWT",
) -> str:
    headers: dict[str, str] = {
        "typ": token_type,
    }

    if key_id is not None:
        headers[
            "kid"
        ] = key_id

    return jwt.encode(
        (
            build_payload()
            if payload is None
            else payload
        ),
        private_key,
        algorithm=algorithm,
        headers=headers,
    )


def build_verifier(
    public_key: str,
) -> JwtServiceTokenVerifier:
    return JwtServiceTokenVerifier(
        public_keys={
            CURRENT_KEY_ID: public_key,
        },
        expected_issuer=CORE_ISSUER,
        expected_audience=INCIDENT_AUDIENCE,
        clock_skew_seconds=5,
        clock=lambda: FIXED_NOW,
    )


def assert_rejected(
    verifier: JwtServiceTokenVerifier,
    token: str,
    reason: ServiceAuthenticationFailureReason,
) -> None:
    with pytest.raises(
        ServiceAuthenticationError,
        match=INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ) as exc_info:
        verifier.verify_token(
            token
        )

    assert exc_info.value.reason is reason
    assert str(
        exc_info.value
    ) == INVALID_SERVICE_CREDENTIALS_MESSAGE


def test_rejects_malformed_and_untrusted_headers(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
) -> None:
    current_pair, _ = key_pairs
    private_key, public_key = current_pair
    verifier = build_verifier(
        public_key
    )

    assert_rejected(
        verifier,
        "not-a-jwt",
        ServiceAuthenticationFailureReason
        .MALFORMED_CREDENTIAL,
    )

    hmac_token = create_token(
        b"adversarial-hmac-secret-at-least-32-bytes",
        algorithm="HS256",
    )
    assert_rejected(
        verifier,
        hmac_token,
        ServiceAuthenticationFailureReason
        .INVALID_ALGORITHM,
    )

    wrong_type = create_token(
        private_key,
        token_type="access+jwt",
    )
    assert_rejected(
        verifier,
        wrong_type,
        ServiceAuthenticationFailureReason
        .INVALID_TOKEN_TYPE,
    )

    missing_key_id = create_token(
        private_key,
        key_id=None,
    )
    assert_rejected(
        verifier,
        missing_key_id,
        ServiceAuthenticationFailureReason
        .MISSING_KEY_ID,
    )

    unknown_key_id = create_token(
        private_key,
        key_id="retired-or-forged-key",
    )
    assert_rejected(
        verifier,
        unknown_key_id,
        ServiceAuthenticationFailureReason
        .UNKNOWN_KEY,
    )


def test_rejects_untrusted_signature_issuer_and_audience(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
) -> None:
    current_pair, attacker_pair = key_pairs
    private_key, public_key = current_pair
    attacker_private_key, _ = attacker_pair
    verifier = build_verifier(
        public_key
    )

    assert_rejected(
        verifier,
        create_token(
            attacker_private_key
        ),
        ServiceAuthenticationFailureReason
        .INVALID_SIGNATURE,
    )

    assert_rejected(
        verifier,
        create_token(
            private_key,
            payload=build_payload(
                iss="forged-issuer",
                sub="forged-issuer",
            ),
        ),
        ServiceAuthenticationFailureReason
        .INVALID_ISSUER,
    )

    assert_rejected(
        verifier,
        create_token(
            private_key,
            payload=build_payload(
                aud="wrong-audience"
            ),
        ),
        ServiceAuthenticationFailureReason
        .INVALID_AUDIENCE,
    )


@pytest.mark.parametrize(
    (
        "payload_overrides",
        "expected_reason",
    ),
    [
        (
            {
                "token_use": "access",
            },
            ServiceAuthenticationFailureReason
            .INVALID_TOKEN_USE,
        ),
        (
            {
                "jti": "not-a-uuid",
            },
            ServiceAuthenticationFailureReason
            .INVALID_CLAIM_CONTRACT,
        ),
        (
            {
                "sub": "forged-subject",
            },
            ServiceAuthenticationFailureReason
            .INVALID_CLAIM_CONTRACT,
        ),
        (
            {
                "iat": "not-a-numeric-date",
            },
            ServiceAuthenticationFailureReason
            .INVALID_CLAIM_CONTRACT,
        ),
        (
            {
                "nbf": (
                    FIXED_NOW
                    + timedelta(
                        seconds=1
                    )
                ),
            },
            ServiceAuthenticationFailureReason
            .INVALID_LIFETIME,
        ),
        (
            {
                "exp": (
                    FIXED_NOW
                    + timedelta(
                        seconds=121
                    )
                ),
            },
            ServiceAuthenticationFailureReason
            .INVALID_LIFETIME,
        ),
        (
            {
                "iat": (
                    FIXED_NOW
                    + timedelta(
                        seconds=30
                    )
                ),
                "nbf": (
                    FIXED_NOW
                    + timedelta(
                        seconds=30
                    )
                ),
                "exp": (
                    FIXED_NOW
                    + timedelta(
                        seconds=90
                    )
                ),
            },
            ServiceAuthenticationFailureReason
            .INVALID_LIFETIME,
        ),
        (
            {
                "iat": (
                    FIXED_NOW
                    - timedelta(
                        seconds=120
                    )
                ),
                "nbf": (
                    FIXED_NOW
                    - timedelta(
                        seconds=120
                    )
                ),
                "exp": (
                    FIXED_NOW
                    - timedelta(
                        seconds=60
                    )
                ),
            },
            ServiceAuthenticationFailureReason
            .INVALID_LIFETIME,
        ),
        (
            {
                "scope": (
                    "incidents:read incidents:read"
                ),
            },
            ServiceAuthenticationFailureReason
            .INVALID_SCOPE_CONTRACT,
        ),
        (
            {
                "scope": "incidents:delete",
            },
            ServiceAuthenticationFailureReason
            .INVALID_SCOPE_CONTRACT,
        ),
    ],
)
def test_rejects_adversarial_claim_contracts(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
    payload_overrides: dict[str, Any],
    expected_reason: ServiceAuthenticationFailureReason,
) -> None:
    current_pair, _ = key_pairs
    private_key, public_key = current_pair

    assert_rejected(
        build_verifier(
            public_key
        ),
        create_token(
            private_key,
            payload=build_payload(
                **payload_overrides
            ),
        ),
        expected_reason,
    )


def test_rejects_missing_required_claim(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
) -> None:
    current_pair, _ = key_pairs
    private_key, public_key = current_pair
    payload = build_payload()
    del payload[
        "exp"
    ]

    assert_rejected(
        build_verifier(
            public_key
        ),
        create_token(
            private_key,
            payload=payload,
        ),
        ServiceAuthenticationFailureReason
        .INVALID_CLAIM_CONTRACT,
    )


def test_valid_token_is_stateless_within_its_short_lifetime(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
) -> None:
    current_pair, _ = key_pairs
    private_key, public_key = current_pair
    verifier = build_verifier(
        public_key
    )
    token = create_token(
        private_key
    )

    first_principal = verifier.verify_token(
        token
    )
    second_principal = verifier.verify_token(
        token
    )

    assert first_principal == second_principal


def test_legacy_and_forged_credentials_share_public_response(
    key_pairs: tuple[
        tuple[str, str],
        tuple[str, str],
    ],
) -> None:
    current_pair, _ = key_pairs
    private_key, public_key = current_pair
    verifier = build_verifier(
        public_key
    )
    application = FastAPI()

    @application.get(
        "/protected"
    )
    def protected(
        principal: Annotated[
            ServicePrincipal,
            Depends(
                dependencies
                .authenticate_service
            ),
        ],
    ) -> dict[str, str]:
        return {
            "subject": (
                principal.subject
            )
        }

    application.dependency_overrides[
        dependencies
        .get_service_token_verifier
    ] = lambda: verifier

    forged_token = create_token(
        private_key,
        key_id="unknown-key",
    )

    with TestClient(
        application
    ) as client:
        legacy_response = client.get(
            "/protected",
            headers={
                "X-OpsFlow-Internal-Token": (
                    "retired-shared-secret"
                ),
            },
        )
        forged_response = client.get(
            "/protected",
            headers={
                "Authorization": (
                    f"Bearer {forged_token}"
                ),
            },
        )

    expected_body = {
        "detail": (
            INVALID_SERVICE_CREDENTIALS_MESSAGE
        )
    }

    assert legacy_response.status_code == 401
    assert forged_response.status_code == 401
    assert legacy_response.json() == expected_body
    assert forged_response.json() == expected_body
    assert (
        legacy_response.headers[
            "WWW-Authenticate"
        ]
        == "Bearer"
    )
    assert (
        forged_response.headers[
            "WWW-Authenticate"
        ]
        == "Bearer"
    )
    assert "retired-shared-secret" not in (
        legacy_response.text
    )
    assert forged_token not in (
        forged_response.text
    )
