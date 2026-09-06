from datetime import (
    datetime,
    timedelta,
    timezone,
)
from uuid import UUID, uuid4

import jwt

from jwt.exceptions import (
    InvalidTokenError as PyJWTInvalidTokenError,
)

from pwdlib import PasswordHash

from app.core.config import settings


JWT_ALGORITHM = settings.jwt_algorithm

ACCESS_TOKEN_TYPE = "access"

REFRESH_TOKEN_TYPE = "refresh"


password_hasher = (
    PasswordHash.recommended()
)


DUMMY_PASSWORD_HASH = (
    password_hasher.hash(
        "opsflow-dummy-password"
    )
)


class TokenValidationError(ValueError):
    """
    Raised when a JWT cannot be trusted as
    a valid OpsFlow token.
    """

    pass


# ---------------------------------------------------------
# Password hashing
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Internal JWT creation
# ---------------------------------------------------------

def _create_token(
    user_id: UUID,
    *,
    token_type: str,
    expires_delta: timedelta,
    signing_secret: str,
) -> str:
    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now + expires_delta
    )

    payload = {
        # Authenticated identity.
        "sub": str(user_id),

        # Token validity window.
        "iat": now,
        "nbf": now,
        "exp": expires_at,

        # OpsFlow trust boundaries.
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,

        # Prevent access/refresh token confusion.
        "type": token_type,

        # Unique identity for this individual token.
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        signing_secret,
        algorithm=JWT_ALGORITHM,
        headers={
            "typ": "JWT",
        },
    )


# ---------------------------------------------------------
# Access token creation
# ---------------------------------------------------------

def create_access_token(
    user_id: UUID,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(
            minutes=(
                settings
                .access_token_expire_minutes
            )
        )

    return _create_token(
        user_id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=expires_delta,
        signing_secret=(
            settings
            .jwt_secret_key
            .get_secret_value()
        ),
    )


# ---------------------------------------------------------
# Refresh token creation
# ---------------------------------------------------------

def create_refresh_token(
    user_id: UUID,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(
            days=(
                settings
                .refresh_token_expire_days
            )
        )

    return _create_token(
        user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=expires_delta,
        signing_secret=(
            settings
            .jwt_refresh_secret_key
            .get_secret_value()
        ),
    )


# ---------------------------------------------------------
# Internal JWT validation
# ---------------------------------------------------------

def _decode_token(
    token: str,
    *,
    expected_type: str,
    signing_secret: str,
) -> UUID:
    try:
        payload = jwt.decode(
            token,
            signing_secret,
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
            "The token is invalid."
        ) from exc

    # -----------------------------------------------------
    # TOKEN TYPE
    # -----------------------------------------------------

    token_type = payload.get(
        "type"
    )

    if token_type != expected_type:
        raise TokenValidationError(
            "The token type is invalid."
        )

    # -----------------------------------------------------
    # JWT ID
    # -----------------------------------------------------

    token_id = payload.get(
        "jti"
    )

    if not isinstance(
        token_id,
        str,
    ):
        raise TokenValidationError(
            "The token identifier is invalid."
        )

    try:
        UUID(token_id)

    except ValueError as exc:
        raise TokenValidationError(
            "The token identifier is invalid."
        ) from exc

    # -----------------------------------------------------
    # SUBJECT
    # -----------------------------------------------------

    subject = payload.get(
        "sub"
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


# ---------------------------------------------------------
# Public token decoders
# ---------------------------------------------------------

def decode_access_token(
    token: str,
) -> UUID:
    return _decode_token(
        token,
        expected_type=(
            ACCESS_TOKEN_TYPE
        ),
        signing_secret=(
            settings
            .jwt_secret_key
            .get_secret_value()
        ),
    )


def decode_refresh_token(
    token: str,
) -> UUID:
    return _decode_token(
        token,
        expected_type=(
            REFRESH_TOKEN_TYPE
        ),
        signing_secret=(
            settings
            .jwt_refresh_secret_key
            .get_secret_value()
        ),
    )