from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import hashlib
import hmac
import secrets
from uuid import UUID, uuid4

import jwt
from jwt.exceptions import (
    InvalidTokenError as PyJWTInvalidTokenError,
)
from pwdlib import PasswordHash

from app.core.config import settings


JWT_ALGORITHM = "HS256"

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


# =========================================================
# TOKEN DOMAIN VALUES
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RefreshTokenClaims:
    """
    Trusted claims extracted from a validated OpsFlow
    refresh token.

    user_id
        User that owns the authentication session.

    session_id
        Stable ID of the server-side auth_sessions row.

    token_id
        ID of this individual refresh token. This must match
        auth_sessions.current_jti.

    expires_at
        Signed expiration timestamp from the JWT.
    """

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
    Raised when a JWT cannot be trusted as a valid OpsFlow
    token.
    """

    pass


# =========================================================
# PASSWORD HASHING
# =========================================================


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
# ACCESS TOKENS
# =========================================================


def create_access_token(
    user_id: UUID,
    *,
    expires_delta: (
        timedelta | None
    ) = None,
) -> str:
    """
    Create a short-lived bearer access token.

    Access tokens remain intentionally stateless in C-2.

    Persistent session validation applies to refresh
    credentials rather than every ordinary API request.
    """

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
        algorithm=JWT_ALGORITHM,
        headers={
            "typ": "JWT",
        },
    )


def decode_access_token(
    token: str,
) -> UUID:
    """
    Validate an OpsFlow access token and return its user ID.
    """

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

    token_type = (
        payload.get(
            "type"
        )
    )

    if (
        token_type
        != ACCESS_TOKEN_TYPE
    ):
        raise TokenValidationError(
            "The token is not an "
            "access token."
        )

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
            "The token identifier "
            "is invalid."
        )

    try:
        UUID(
            token_id
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The token identifier "
            "is invalid."
        ) from exc

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
            "The token subject "
            "is invalid."
        )

    try:
        return UUID(
            subject
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The token subject "
            "is invalid."
        ) from exc


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
    Create a refresh JWT bound to a persistent
    authentication session.

    sid
        Stable server-side authentication-session ID.

    jti
        ID of this specific refresh credential.

    During C-2, jti is checked against
    auth_sessions.current_jti.

    C-3 will atomically replace current_jti whenever the
    credential is successfully rotated.
    """

    now = datetime.now(
        timezone.utc
    )

    if expires_at.tzinfo is None:
        raise ValueError(
            "Refresh-token expiration "
            "must be timezone-aware."
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
        algorithm=JWT_ALGORITHM,
        headers={
            "typ": "JWT",
        },
    )


def decode_refresh_token(
    token: str,
) -> RefreshTokenClaims:
    """
    Fully validate a refresh JWT and return trusted claims.

    This verifies the cryptographic JWT itself.

    It does NOT by itself establish that the server-side
    authentication session is still valid. That second
    trust decision belongs to AuthenticationService.
    """

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

    token_type = (
        payload.get(
            "type"
        )
    )

    if (
        token_type
        != REFRESH_TOKEN_TYPE
    ):
        raise TokenValidationError(
            "The token is not a "
            "refresh token."
        )

    subject = (
        payload.get(
            "sub"
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
        subject,
        str,
    ):
        raise TokenValidationError(
            "The refresh-token subject "
            "is invalid."
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
            (int, float),
        )
    ):
        raise TokenValidationError(
            "The refresh-token expiration "
            "is invalid."
        )

    try:
        user_id = UUID(
            subject
        )

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
        OverflowError,
        OSError,
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
# SESSION-BOUND CSRF TOKENS
# =========================================================


def _csrf_signature(
    *,
    session_id: UUID,
    nonce: str,
) -> str:
    """
    Produce an HMAC signature binding a CSRF nonce to one
    persistent authentication session.
    """

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
    """
    Create a JavaScript-readable CSRF token that is valid
    only for the specified authentication session.
    """

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
    """
    Verify a signed CSRF token for a specific persistent
    authentication session.
    """

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