from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
)
from dataclasses import (
    dataclass,
)
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from enum import (
    StrEnum,
)
from typing import (
    Any,
    Protocol,
)
from uuid import (
    UUID,
)

import jwt
from cryptography.exceptions import (
    UnsupportedAlgorithm,
)
from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    load_pem_public_key,
)
from jwt.exceptions import (
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    PyJWTError,
)

from app.core.service_identity import (
    MAXIMUM_SERVICE_TOKEN_TTL_SECONDS,
    MINIMUM_RSA_KEY_SIZE,
    MINIMUM_SERVICE_TOKEN_TTL_SECONDS,
    SERVICE_TOKEN_ALGORITHM,
    SERVICE_TOKEN_USE,
    ServiceIdentityConfigurationError,
    ServiceIdentityError,
    ServiceScope,
)

SERVICE_TOKEN_TYPE = "JWT"

DEFAULT_CLOCK_SKEW_SECONDS = 5
MAXIMUM_CLOCK_SKEW_SECONDS = 30

MAXIMUM_VERIFICATION_KEYS = 2

INVALID_SERVICE_CREDENTIALS_MESSAGE = (
    "Invalid service credentials."
)


class ServiceAuthenticationFailureReason(
    StrEnum
):
    MALFORMED_CREDENTIAL = "malformed_credential"
    INVALID_ALGORITHM = "invalid_algorithm"
    INVALID_TOKEN_TYPE = "invalid_token_type"
    MISSING_KEY_ID = "missing_key_id"
    UNKNOWN_KEY = "unknown_key"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_ISSUER = "invalid_issuer"
    INVALID_AUDIENCE = "invalid_audience"
    INVALID_CLAIM_CONTRACT = "invalid_claim_contract"
    INVALID_TOKEN_USE = "invalid_token_use"
    INVALID_LIFETIME = "invalid_lifetime"
    INVALID_SCOPE_CONTRACT = "invalid_scope_contract"


class ServiceAuthenticationError(
    ServiceIdentityError
):
    """
    Raised when a service credential cannot be trusted.

    The public message is deliberately generic. The bounded
    reason is safe for internal metrics and security events.
    """

    def __init__(
        self,
        message: str = INVALID_SERVICE_CREDENTIALS_MESSAGE,
        *,
        reason: ServiceAuthenticationFailureReason = (
            ServiceAuthenticationFailureReason
            .INVALID_CLAIM_CONTRACT
        ),
    ) -> None:
        super().__init__(
            message
        )
        self.reason = reason


@dataclass(
    frozen=True,
    slots=True,
)
class ServicePrincipal:
    issuer: str
    subject: str
    audience: str
    token_id: UUID
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    scopes: frozenset[
        ServiceScope
    ]


class ServiceTokenVerifier(
    Protocol
):
    def verify_token(
        self,
        token: str,
    ) -> ServicePrincipal:
        ...


def utc_now(
) -> datetime:
    return datetime.now(
        UTC
    )


def _configuration_text(
    value: str,
    *,
    field_name: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise (
            ServiceIdentityConfigurationError(
                f"{field_name} must be a string."
            )
        )

    normalized_value = (
        value.strip()
    )

    if not normalized_value:
        raise (
            ServiceIdentityConfigurationError(
                f"{field_name} must not be empty."
            )
        )

    return normalized_value


def _authentication_error(
    reason: ServiceAuthenticationFailureReason = (
        ServiceAuthenticationFailureReason
        .INVALID_CLAIM_CONTRACT
    ),
) -> ServiceAuthenticationError:
    return ServiceAuthenticationError(
        reason=reason
    )


class JwtServiceTokenVerifier:
    """
    Verify short-lived RS256 service JWTs.

    The verifier accepts one current public key and,
    optionally, one previous public key during rotation.
    Key selection occurs only through the protected `kid`
    contract and the algorithm is fixed to RS256.
    """

    def __init__(
        self,
        *,
        public_keys: Mapping[
            str,
            str,
        ],
        expected_issuer: str,
        expected_audience: str,
        clock_skew_seconds: int = (
            DEFAULT_CLOCK_SKEW_SECONDS
        ),
        clock: Callable[
            [],
            datetime,
        ] = utc_now,
    ) -> None:
        self._expected_issuer = (
            _configuration_text(
                expected_issuer,
                field_name=(
                    "expected_issuer"
                ),
            )
        )

        self._expected_audience = (
            _configuration_text(
                expected_audience,
                field_name=(
                    "expected_audience"
                ),
            )
        )

        if (
            isinstance(
                clock_skew_seconds,
                bool,
            )
            or not isinstance(
                clock_skew_seconds,
                int,
            )
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "clock_skew_seconds must be "
                    "an integer."
                )
            )

        if not (
            0
            <= clock_skew_seconds
            <= MAXIMUM_CLOCK_SKEW_SECONDS
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "clock_skew_seconds must be between "
                    "0 and "
                    f"{MAXIMUM_CLOCK_SKEW_SECONDS}."
                )
            )

        if not callable(
            clock
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "clock must be callable."
                )
            )

        if not isinstance(
            public_keys,
            Mapping,
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "public_keys must be a mapping."
                )
            )

        if not public_keys:
            raise (
                ServiceIdentityConfigurationError(
                    "At least one service verification "
                    "key is required."
                )
            )

        if (
            len(
                public_keys
            )
            > MAXIMUM_VERIFICATION_KEYS
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "At most two service verification "
                    "keys are allowed."
                )
            )

        loaded_keys: dict[
            str,
            RSAPublicKey,
        ] = {}

        for key_id, public_key_pem in (
            public_keys.items()
        ):
            normalized_key_id = (
                _configuration_text(
                    key_id,
                    field_name="key_id",
                )
            )

            if not isinstance(
                public_key_pem,
                str,
            ):
                raise (
                    ServiceIdentityConfigurationError(
                        "public_key_pem must be a string."
                    )
                )

            try:
                loaded_key = (
                    load_pem_public_key(
                        public_key_pem.encode(
                            "utf-8"
                        )
                    )
                )

            except (
                TypeError,
                UnsupportedAlgorithm,
                ValueError,
            ) as exc:
                raise (
                    ServiceIdentityConfigurationError(
                        "public_key_pem is not a valid "
                        "PEM public key."
                    )
                ) from exc

            if not isinstance(
                loaded_key,
                RSAPublicKey,
            ):
                raise (
                    ServiceIdentityConfigurationError(
                        "public_key_pem must contain "
                        "an RSA public key."
                    )
                )

            if (
                loaded_key.key_size
                < MINIMUM_RSA_KEY_SIZE
            ):
                raise (
                    ServiceIdentityConfigurationError(
                        "RSA public keys must be at least "
                        f"{MINIMUM_RSA_KEY_SIZE} bits."
                    )
                )

            loaded_keys[
                normalized_key_id
            ] = loaded_key

        self._public_keys = loaded_keys

        self._clock_skew = timedelta(
            seconds=(
                clock_skew_seconds
            )
        )

        self._clock = clock

    def verify_token(
        self,
        token: str,
    ) -> ServicePrincipal:
        if (
            not isinstance(
                token,
                str,
            )
            or not token.strip()
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .MALFORMED_CREDENTIAL
                )
            )

        try:
            header = (
                jwt.get_unverified_header(
                    token
                )
            )

        except PyJWTError:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .MALFORMED_CREDENTIAL
                )
            ) from None

        if header.get("alg") != SERVICE_TOKEN_ALGORITHM:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_ALGORITHM
                )
            )

        if header.get("typ") != SERVICE_TOKEN_TYPE:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_TOKEN_TYPE
                )
            )

        key_id = header.get(
            "kid"
        )

        if (
            not isinstance(
                key_id,
                str,
            )
            or not key_id
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .MISSING_KEY_ID
                )
            )

        public_key = (
            self
            ._public_keys
            .get(
                key_id
            )
        )

        if public_key is None:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .UNKNOWN_KEY
                )
            )

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=[
                    SERVICE_TOKEN_ALGORITHM
                ],
                audience=(
                    self
                    ._expected_audience
                ),
                issuer=(
                    self
                    ._expected_issuer
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
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                },
            )

        except InvalidSignatureError:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_SIGNATURE
                )
            ) from None

        except InvalidIssuerError:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_ISSUER
                )
            ) from None

        except InvalidAudienceError:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_AUDIENCE
                )
            ) from None

        except PyJWTError:
            raise (
                _authentication_error()
            ) from None

        return self._principal_from_payload(
            payload
        )

    def _principal_from_payload(
        self,
        payload: Mapping[
            str,
            Any,
        ],
    ) -> ServicePrincipal:
        issuer = payload.get(
            "iss"
        )

        subject = payload.get(
            "sub"
        )

        audience = payload.get(
            "aud"
        )

        if (
            not isinstance(
                issuer,
                str,
            )
            or not isinstance(
                subject,
                str,
            )
            or not isinstance(
                audience,
                str,
            )
        ):
            raise (
                _authentication_error()
            )

        if (
            issuer
            != self._expected_issuer
            or subject
            != self._expected_issuer
            or audience
            != self._expected_audience
        ):
            raise (
                _authentication_error()
            )

        if payload.get(
            "token_use"
        ) != SERVICE_TOKEN_USE:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_TOKEN_USE
                )
            )

        token_id_value = payload.get(
            "jti"
        )

        if not isinstance(
            token_id_value,
            str,
        ):
            raise (
                _authentication_error()
            )

        try:
            token_id = UUID(
                token_id_value
            )

        except ValueError:
            raise (
                _authentication_error()
            ) from None

        issued_at = self._numeric_date(
            payload,
            "iat",
        )

        not_before = self._numeric_date(
            payload,
            "nbf",
        )

        expires_at = self._numeric_date(
            payload,
            "exp",
        )

        if not_before != issued_at:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_LIFETIME
                )
            )

        token_lifetime = (
            expires_at
            - issued_at
        )

        if not (
            timedelta(
                seconds=(
                    MINIMUM_SERVICE_TOKEN_TTL_SECONDS
                )
            )
            <= token_lifetime
            <= timedelta(
                seconds=(
                    MAXIMUM_SERVICE_TOKEN_TTL_SECONDS
                )
            )
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_LIFETIME
                )
            )

        now = self._clock()

        if (
            not isinstance(
                now,
                datetime,
            )
            or now.tzinfo
            is None
            or now.utcoffset()
            is None
        ):
            raise (
                ServiceIdentityConfigurationError(
                    "The service-token verifier clock "
                    "must return a timezone-aware "
                    "datetime."
                )
            )

        now = now.astimezone(
            UTC
        )

        if (
            issued_at
            > now
            + self._clock_skew
            or not_before
            > now
            + self._clock_skew
            or now
            >= expires_at
            + self._clock_skew
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_LIFETIME
                )
            )

        scopes = self._scopes(
            payload
        )

        return ServicePrincipal(
            issuer=issuer,
            subject=subject,
            audience=audience,
            token_id=token_id,
            issued_at=issued_at,
            not_before=not_before,
            expires_at=expires_at,
            scopes=scopes,
        )

    @staticmethod
    def _numeric_date(
        payload: Mapping[
            str,
            Any,
        ],
        claim_name: str,
    ) -> datetime:
        value = payload.get(
            claim_name
        )

        if (
            isinstance(
                value,
                bool,
            )
            or not isinstance(
                value,
                int | float,
            )
        ):
            raise (
                _authentication_error()
            )

        try:
            return datetime.fromtimestamp(
                value,
                tz=UTC,
            )

        except (
            OSError,
            OverflowError,
            ValueError,
        ):
            raise (
                _authentication_error()
            ) from None

    @staticmethod
    def _scopes(
        payload: Mapping[
            str,
            Any,
        ],
    ) -> frozenset[
        ServiceScope
    ]:
        scope_value = payload.get(
            "scope"
        )

        if not isinstance(
            scope_value,
            str,
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_SCOPE_CONTRACT
                )
            )

        scope_names = (
            scope_value.split()
        )

        if (
            not scope_names
            or len(
                scope_names
            )
            != len(
                set(
                    scope_names
                )
            )
        ):
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_SCOPE_CONTRACT
                )
            )

        try:
            return frozenset(
                ServiceScope(
                    scope_name
                )
                for scope_name
                in scope_names
            )

        except ValueError:
            raise (
                _authentication_error(
                    ServiceAuthenticationFailureReason
                    .INVALID_SCOPE_CONTRACT
                )
            ) from None
