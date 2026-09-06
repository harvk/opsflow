from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import InvalidTokenError as PyJWTInvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"


password_hasher = PasswordHash.recommended()


DUMMY_PASSWORD_HASH = password_hasher.hash(
    "opsflow-dummy-password"
)


class TokenValidationError(ValueError):
    """
    Raised when a JWT cannot be trusted as a valid
    OpsFlow access token.
    """

    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(
    user_id: UUID,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a signed OpsFlow access token.

    The token contains:

    sub
        The authenticated user's UUID.

    iat
        The time at which the token was issued.

    nbf
        The time before which the token must not be accepted.

    exp
        The time at which the token expires.

    iss
        The trusted OpsFlow token issuer.

    aud
        The intended token audience.

    type
        Identifies this JWT specifically as an access token.

    jti
        A unique identifier for this individual token.
    """

    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    expires_at = now + expires_delta

    payload = {
        "sub": str(user_id),

        # Security timestamps
        "iat": now,
        "nbf": now,
        "exp": expires_at,

        # Token trust boundaries
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,

        # Prevent token-type confusion
        "type": ACCESS_TOKEN_TYPE,

        # Unique token/session identifier
        "jti": str(uuid4()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
        headers={
            "typ": "JWT",
        },
    )


def decode_access_token(
    token: str,
) -> UUID:
    """
    Validate and decode an OpsFlow access token.

    Returns the authenticated user's UUID when the token
    satisfies every required security invariant.

    Raises TokenValidationError when validation fails.
    """

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
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

    # ---------------------------------------------------------
    # TOKEN TYPE
    # ---------------------------------------------------------

    token_type = payload.get("type")

    if token_type != ACCESS_TOKEN_TYPE:
        raise TokenValidationError(
            "The token is not an access token."
        )

    # ---------------------------------------------------------
    # JWT ID
    # ---------------------------------------------------------

    token_id = payload.get("jti")

    if not isinstance(token_id, str):
        raise TokenValidationError(
            "The token identifier is invalid."
        )

    try:
        UUID(token_id)
    except ValueError as exc:
        raise TokenValidationError(
            "The token identifier is invalid."
        ) from exc

    # ---------------------------------------------------------
    # SUBJECT
    # ---------------------------------------------------------

    subject = payload.get("sub")

    if not isinstance(subject, str):
        raise TokenValidationError(
            "The token subject is invalid."
        )

    try:
        return UUID(subject)

    except ValueError as exc:
        raise TokenValidationError(
            "The token subject is invalid."
        ) from exc