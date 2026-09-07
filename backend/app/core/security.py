from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import hashlib
import hmac
import secrets

from uuid import (
    UUID,
    uuid4,
)

import jwt

from jwt.exceptions import (
    InvalidTokenError as PyJWTInvalidTokenError,
)

from pwdlib import (
    PasswordHash,
)

from app.core.config import (
    settings,
)


# =========================================================
# TOKEN TYPES
# =========================================================

JWT_ALGORITHM = (
    "HS256"
)

ACCESS_TOKEN_TYPE = (
    "access"
)

REFRESH_TOKEN_TYPE = (
    "refresh"
)

REAUTH_TOKEN_TYPE = (
    "reauth"
)


# =========================================================
# PASSWORD HASHING
# =========================================================

password_hasher = (
    PasswordHash.recommended()
)


DUMMY_PASSWORD_HASH = (
    password_hasher.hash(
        "opsflow-dummy-password"
    )
)


def hash_password(
    password: str,
) -> str:
    return password_hasher.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


# =========================================================
# TOKEN DOMAIN VALUES
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RefreshTokenClaims:
    user_id: UUID
    session_id: UUID
    token_id: UUID
    expires_at: datetime


# =========================================================
# SECURITY EXCEPTIONS
# =========================================================


class TokenValidationError(
    ValueError
):
    """
    Raised when a JWT cannot be trusted.
    """

    pass


# =========================================================
# ACCESS TOKENS
# =========================================================


def create_access_token(
    user_id: UUID,
    *,
    expires_delta: (
        timedelta | None
    ) = None,
) -> str:
    now = datetime.now(
        timezone.utc
    )

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=(
                settings
                .access_token_expire_minutes
            )
        )

    expires_at = (
        now + expires_delta
    )

    payload = {
        "sub": str(
            user_id
        ),
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": (
            settings.jwt_issuer
        ),
        "aud": (
            settings.jwt_audience
        ),
        "type": (
            ACCESS_TOKEN_TYPE
        ),
        "jti": str(
            uuid4()
        ),
    }

    return jwt.encode(
        payload,
        (
            settings
            .jwt_secret_key
            .get_secret_value()
        ),
        algorithm=(
            JWT_ALGORITHM
        ),
        headers={
            "typ": "JWT",
        },
    )


def decode_access_token(
    token: str,
) -> UUID:
    try:
        payload = jwt.decode(
            token,
            (
                settings
                .jwt_secret_key
                .get_secret_value()
            ),
            algorithms=[
                JWT_ALGORITHM
            ],
            issuer=(
                settings.jwt_issuer
            ),
            audience=(
                settings.jwt_audience
            ),
            options={
                "require": [
                    "sub",
                    "iat",
                    "nbf",
                    "exp",
                    "iss",
                    "aud",
                    "type",
                    "jti",
                ]
            },
        )

    except PyJWTInvalidTokenError as exc:
        raise TokenValidationError(
            "The access token is invalid."
        ) from exc

    if (
        payload.get(
            "type"
        )
        != ACCESS_TOKEN_TYPE
    ):
        raise TokenValidationError(
            "The token is not an "
            "access token."
        )

    _validate_jti(
        payload
    )

    return _decode_subject(
        payload
    )


# =========================================================
# REFRESH TOKENS
# =========================================================


def create_refresh_token(
    user_id: UUID,
    *,
    session_id: UUID,
    token_id: UUID,
    expires_at: datetime,
) -> str:
    """
    Create a refresh JWT bound to one persistent
    authentication session.
    """

    if expires_at.tzinfo is None:
        raise ValueError(
            "Refresh-token expiration "
            "must be timezone-aware."
        )

    now = datetime.now(
        timezone.utc
    )

    payload = {
        "sub": str(
            user_id
        ),
        "sid": str(
            session_id
        ),
        "jti": str(
            token_id
        ),
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": (
            settings.jwt_issuer
        ),
        "aud": (
            settings.jwt_audience
        ),
        "type": (
            REFRESH_TOKEN_TYPE
        ),
    }

    return jwt.encode(
        payload,
        (
            settings
            .jwt_refresh_secret_key
            .get_secret_value()
        ),
        algorithm=(
            JWT_ALGORITHM
        ),
        headers={
            "typ": "JWT",
        },
    )


def decode_refresh_token(
    token: str,
) -> RefreshTokenClaims:
    try:
        payload = jwt.decode(
            token,
            (
                settings
                .jwt_refresh_secret_key
                .get_secret_value()
            ),
            algorithms=[
                JWT_ALGORITHM
            ],
            issuer=(
                settings.jwt_issuer
            ),
            audience=(
                settings.jwt_audience
            ),
            options={
                "require": [
                    "sub",
                    "sid",
                    "jti",
                    "iat",
                    "nbf",
                    "exp",
                    "iss",
                    "aud",
                    "type",
                ]
            },
        )

    except PyJWTInvalidTokenError as exc:
        raise TokenValidationError(
            "The refresh token is invalid."
        ) from exc

    if (
        payload.get(
            "type"
        )
        != REFRESH_TOKEN_TYPE
    ):
        raise TokenValidationError(
            "The token is not a "
            "refresh token."
        )

    user_id = (
        _decode_subject(
            payload
        )
    )

    session_value = (
        payload.get(
            "sid"
        )
    )

    token_value = (
        payload.get(
            "jti"
        )
    )

    expires_value = (
        payload.get(
            "exp"
        )
    )

    if not isinstance(
        session_value,
        str,
    ):
        raise TokenValidationError(
            "The refresh-token session "
            "identifier is invalid."
        )

    if not isinstance(
        token_value,
        str,
    ):
        raise TokenValidationError(
            "The refresh-token identifier "
            "is invalid."
        )

    if (
        isinstance(
            expires_value,
            bool,
        )
        or not isinstance(
            expires_value,
            (
                int,
                float,
            ),
        )
    ):
        raise TokenValidationError(
            "The refresh-token expiration "
            "is invalid."
        )

    try:
        session_id = UUID(
            session_value
        )

        token_id = UUID(
            token_value
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The refresh token contains "
            "an invalid UUID claim."
        ) from exc

    try:
        expires_at = (
            datetime.fromtimestamp(
                float(
                    expires_value
                ),
                tz=timezone.utc,
            )
        )

    except (
        OSError,
        OverflowError,
        ValueError,
    ) as exc:
        raise TokenValidationError(
            "The refresh-token expiration "
            "is invalid."
        ) from exc

    return RefreshTokenClaims(
        user_id=user_id,
        session_id=session_id,
        token_id=token_id,
        expires_at=expires_at,
    )


# =========================================================
# REAUTHENTICATION TOKENS
# =========================================================


def create_reauthentication_token(
    user_id: UUID,
    *,
    expires_delta: (
        timedelta | None
    ) = None,
) -> str:
    """
    Create a very short-lived JWT proving that the user
    recently supplied their current password.

    This token is deliberately distinct from:

        access JWT
        refresh JWT

    It must never be accepted as either of those token types.
    """

    now = datetime.now(
        timezone.utc
    )

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=(
                settings
                .reauth_token_expire_minutes
            )
        )

    expires_at = (
        now + expires_delta
    )

    payload = {
        "sub": str(
            user_id
        ),
        "iat": now,
        "nbf": now,
        "exp": expires_at,
        "iss": (
            settings.jwt_issuer
        ),
        "aud": (
            settings.jwt_audience
        ),
        "type": (
            REAUTH_TOKEN_TYPE
        ),
        "jti": str(
            uuid4()
        ),
    }

    return jwt.encode(
        payload,
        (
            settings
            .jwt_reauth_secret_key
            .get_secret_value()
        ),
        algorithm=(
            JWT_ALGORITHM
        ),
        headers={
            "typ": "JWT",
        },
    )


def decode_reauthentication_token(
    token: str,
) -> UUID:
    """
    Validate a short-lived sensitive-action reauthentication
    credential and return its subject.
    """

    try:
        payload = jwt.decode(
            token,
            (
                settings
                .jwt_reauth_secret_key
                .get_secret_value()
            ),
            algorithms=[
                JWT_ALGORITHM
            ],
            issuer=(
                settings.jwt_issuer
            ),
            audience=(
                settings.jwt_audience
            ),
            options={
                "require": [
                    "sub",
                    "iat",
                    "nbf",
                    "exp",
                    "iss",
                    "aud",
                    "type",
                    "jti",
                ]
            },
        )

    except PyJWTInvalidTokenError as exc:
        raise TokenValidationError(
            "The reauthentication "
            "token is invalid."
        ) from exc

    if (
        payload.get(
            "type"
        )
        != REAUTH_TOKEN_TYPE
    ):
        raise TokenValidationError(
            "The token is not a "
            "reauthentication token."
        )

    _validate_jti(
        payload
    )

    return _decode_subject(
        payload
    )


# =========================================================
# SESSION-BOUND CSRF TOKENS
# =========================================================


def _csrf_signature(
    *,
    session_id: UUID,
    nonce: str,
) -> str:
    message = (
        f"{session_id}:{nonce}"
        .encode(
            "utf-8"
        )
    )

    secret = (
        settings
        .csrf_secret_key
        .encode(
            "utf-8"
        )
    )

    return hmac.new(
        secret,
        message,
        hashlib.sha256,
    ).hexdigest()


def create_csrf_token(
    session_id: UUID,
) -> str:
    nonce = (
        secrets.token_urlsafe(
            32
        )
    )

    signature = (
        _csrf_signature(
            session_id=session_id,
            nonce=nonce,
        )
    )

    return (
        f"{nonce}.{signature}"
    )


def validate_csrf_token(
    session_id: UUID,
    csrf_token: str,
) -> bool:
    nonce, separator, supplied_signature = (
        csrf_token.partition(
            "."
        )
    )

    if (
        not separator
        or not nonce
        or not supplied_signature
    ):
        return False

    expected_signature = (
        _csrf_signature(
            session_id=session_id,
            nonce=nonce,
        )
    )

    return hmac.compare_digest(
        supplied_signature.encode(
            "utf-8"
        ),
        expected_signature.encode(
            "utf-8"
        ),
    )


# =========================================================
# SHARED JWT VALIDATION
# =========================================================


def _decode_subject(
    payload: dict,
) -> UUID:
    subject = (
        payload.get(
            "sub"
        )
    )

    if not isinstance(
        subject,
        str,
    ):
        raise TokenValidationError(
            "The token subject is invalid."
        )

    try:
        return UUID(
            subject
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The token subject is invalid."
        ) from exc


def _validate_jti(
    payload: dict,
) -> None:
    token_id = (
        payload.get(
            "jti"
        )
    )

    if not isinstance(
        token_id,
        str,
    ):
        raise TokenValidationError(
            "The token identifier is invalid."
        )

    try:
        UUID(
            token_id
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The token identifier is invalid."
        ) from exc