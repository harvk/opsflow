from datetime import datetime, timedelta, timezone
from uuid import UUID

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
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    expires_at = now + expires_delta

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "type": ACCESS_TOKEN_TYPE,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(
    token: str,
) -> UUID:
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
                    "exp",
                    "iss",
                    "aud",
                    "type",
                ]
            },
        )
    except PyJWTInvalidTokenError as exc:
        raise TokenValidationError(
            "The access token is invalid."
        ) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise TokenValidationError(
            "The token is not an access token."
        )

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