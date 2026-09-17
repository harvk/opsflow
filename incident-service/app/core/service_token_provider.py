from __future__ import annotations

from collections.abc import Callable, Collection
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from jwt.exceptions import PyJWTError

from app.core.config import get_settings
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

DEFAULT_SERVICE_TOKEN_TTL_SECONDS = 60


class ServiceTokenCreationError(ServiceIdentityError):
    """Raised when an outbound service JWT cannot be created."""


class ServiceTokenProvider(Protocol):
    """Boundary for creating short-lived outbound credentials."""

    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[ServiceScope],
    ) -> str:
        ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def _required_text(
    value: str,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ServiceIdentityConfigurationError(
            f"{field_name} must be a string."
        )

    normalized_value = value.strip()

    if not normalized_value:
        raise ServiceIdentityConfigurationError(
            f"{field_name} must not be empty."
        )

    return normalized_value


class JwtServiceTokenProvider:
    """
    Create independently identifiable RS256 service JWTs.

    The caller selects one target audience and the minimum
    scopes required for the outbound operation.
    """

    def __init__(
        self,
        *,
        private_key_pem: str,
        key_id: str,
        issuer: str,
        ttl_seconds: int = DEFAULT_SERVICE_TOKEN_TTL_SECONDS,
        clock: Callable[[], datetime] = utc_now,
        token_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._key_id = _required_text(
            key_id,
            field_name="key_id",
        )
        self._issuer = _required_text(
            issuer,
            field_name="issuer",
        )

        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
            raise ServiceIdentityConfigurationError(
                "ttl_seconds must be an integer."
            )

        if not (
            MINIMUM_SERVICE_TOKEN_TTL_SECONDS
            <= ttl_seconds
            <= MAXIMUM_SERVICE_TOKEN_TTL_SECONDS
        ):
            raise ServiceIdentityConfigurationError(
                "ttl_seconds must be between "
                f"{MINIMUM_SERVICE_TOKEN_TTL_SECONDS} and "
                f"{MAXIMUM_SERVICE_TOKEN_TTL_SECONDS}."
            )

        if not callable(clock):
            raise ServiceIdentityConfigurationError(
                "clock must be callable."
            )

        if not callable(token_id_factory):
            raise ServiceIdentityConfigurationError(
                "token_id_factory must be callable."
            )

        if not isinstance(private_key_pem, str):
            raise ServiceIdentityConfigurationError(
                "private_key_pem must be a string."
            )

        try:
            private_key = load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
            )

        except (TypeError, UnsupportedAlgorithm, ValueError) as exc:
            raise ServiceIdentityConfigurationError(
                "private_key_pem is not a valid "
                "unencrypted PEM private key."
            ) from exc

        if not isinstance(private_key, RSAPrivateKey):
            raise ServiceIdentityConfigurationError(
                "private_key_pem must contain an RSA private key."
            )

        if private_key.key_size < MINIMUM_RSA_KEY_SIZE:
            raise ServiceIdentityConfigurationError(
                "RSA private keys must be at least "
                f"{MINIMUM_RSA_KEY_SIZE} bits."
            )

        self._private_key = private_key
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._token_id_factory = token_id_factory

    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[ServiceScope],
    ) -> str:
        normalized_audience = _required_text(
            audience,
            field_name="audience",
        )
        normalized_scopes: set[ServiceScope] = set()

        for scope in scopes:
            if not isinstance(scope, ServiceScope):
                raise ServiceTokenCreationError(
                    "Every service scope must be a ServiceScope value."
                )

            normalized_scopes.add(scope)

        if not normalized_scopes:
            raise ServiceTokenCreationError(
                "At least one service scope is required."
            )

        issued_at = self._clock()

        if (
            not isinstance(issued_at, datetime)
            or issued_at.tzinfo is None
            or issued_at.utcoffset() is None
        ):
            raise ServiceTokenCreationError(
                "The service-token clock must return "
                "a timezone-aware datetime."
            )

        issued_at = issued_at.astimezone(UTC)
        token_id = self._token_id_factory()

        if not isinstance(token_id, UUID):
            raise ServiceTokenCreationError(
                "The service-token ID factory must return a UUID."
            )

        expires_at = issued_at + timedelta(seconds=self._ttl_seconds)
        scope_value = " ".join(
            sorted(scope.value for scope in normalized_scopes)
        )

        payload = {
            "iss": self._issuer,
            "sub": self._issuer,
            "aud": normalized_audience,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": expires_at,
            "jti": str(token_id),
            "token_use": SERVICE_TOKEN_USE,
            "scope": scope_value,
        }

        try:
            return jwt.encode(
                payload,
                self._private_key,
                algorithm=SERVICE_TOKEN_ALGORITHM,
                headers={
                    "typ": "JWT",
                    "kid": self._key_id,
                },
            )

        except (PyJWTError, TypeError, ValueError) as exc:
            raise ServiceTokenCreationError(
                "The service credential could not be created."
            ) from exc


def build_service_token_provider(
    *,
    private_key_path: Path,
    key_id: str,
    issuer: str,
    ttl_seconds: int,
) -> ServiceTokenProvider:
    """Load an unencrypted PEM key and build a provider."""

    try:
        private_key_pem = private_key_path.read_text(encoding="utf-8")

    except (OSError, UnicodeError) as exc:
        raise ServiceIdentityConfigurationError(
            "The service-identity private key could not be loaded."
        ) from exc

    return JwtServiceTokenProvider(
        private_key_pem=private_key_pem,
        key_id=key_id,
        issuer=issuer,
        ttl_seconds=ttl_seconds,
    )


@lru_cache(maxsize=1)
def get_service_token_provider() -> ServiceTokenProvider:
    """Construct the process-wide Incident signing provider."""

    settings = get_settings()

    return build_service_token_provider(
        private_key_path=(
            settings.service_identity_signing_private_key_path
        ),
        key_id=settings.service_identity_signing_key_id,
        issuer=settings.service_identity_signing_issuer,
        ttl_seconds=(
            settings.service_identity_signing_token_ttl_seconds
        ),
    )
