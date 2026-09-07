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
    """
    Hash a plaintext password using the application's
    configured recommended password-hashing algorithm.
    """

    return password_hasher.hash(
        password
    )


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify a plaintext password against a stored password
    hash.
    """

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
    """
    Trusted claims extracted from a validated refresh JWT.
    """

    user_id: UUID
    session_id: UUID
    token_id: UUID
    expires_at: datetime


@dataclass(
    frozen=True,
    slots=True,
)
class ReauthenticationClaims:
    """
    Trusted claims extracted from a validated
    reauthentication JWT.

    credential_fingerprint binds the reauthentication proof
    to the password hash that existed when the user supplied
    their current password.
    """

    user_id: UUID
    token_id: UUID
    credential_fingerprint: str


# =========================================================
# SECURITY EXCEPTIONS
# =========================================================


class TokenValidationError(
    ValueError
):
    """
    Raised when a JWT cannot be cryptographically or
    structurally trusted.

    Higher-level services translate this low-level security
    exception into authentication-domain exceptions.
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
    """
    Create a short-lived bearer access JWT.
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
    """
    Decode and validate a bearer access JWT.

    Returns the authenticated user's UUID.
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

    sid:
        stable authentication-session identifier

    jti:
        identity of the current one-time refresh credential
    """

    if (
        expires_at.tzinfo
        is None
    ):
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
    """
    Decode and validate a persistent-session refresh JWT.
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
        user_id=(
            user_id
        ),
        session_id=(
            session_id
        ),
        token_id=(
            token_id
        ),
        expires_at=(
            expires_at
        ),
    )


# =========================================================
# REAUTHENTICATION CREDENTIAL FINGERPRINT
# =========================================================


def create_reauthentication_fingerprint(
    hashed_password: str,
) -> str:
    """
    Create a keyed fingerprint of the user's currently
    stored password hash.

    This allows a reauthentication JWT to be invalidated
    automatically when the stored password hash changes.

    Neither the plaintext password nor the password hash is
    placed into the JWT.
    """

    secret = (
        settings
        .jwt_reauth_secret_key
        .get_secret_value()
        .encode(
            "utf-8"
        )
    )

    message = (
        "opsflow-reauth-credential:"
        f"{hashed_password}"
    ).encode(
        "utf-8"
    )

    return hmac.new(
        secret,
        message,
        hashlib.sha256,
    ).hexdigest()


def reauthentication_credential_matches(
    *,
    hashed_password: str,
    credential_fingerprint: str,
) -> bool:
    """
    Determine whether a reauthentication JWT was issued
    against the user's currently stored password hash.

    If the password hash changed after the token was issued,
    the calculated fingerprint will no longer match.
    """

    expected_fingerprint = (
        create_reauthentication_fingerprint(
            hashed_password
        )
    )

    return hmac.compare_digest(
        expected_fingerprint.encode(
            "utf-8"
        ),
        credential_fingerprint.encode(
            "utf-8"
        ),
    )


# =========================================================
# REAUTHENTICATION TOKENS
# =========================================================


def create_reauthentication_token(
    user_id: UUID,
    *,
    credential_hash: str,
    expires_delta: (
        timedelta | None
    ) = None,
) -> str:
    """
    Create short-lived proof of recent password
    verification.

    credential_hash is the user's currently stored password
    hash.

    The password hash itself is never placed inside the JWT.
    Instead, the JWT receives an HMAC credential
    fingerprint.
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

    token_id = (
        uuid4()
    )

    credential_fingerprint = (
        create_reauthentication_fingerprint(
            credential_hash
        )
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
            token_id
        ),

        # cv = credential-version fingerprint.
        #
        # This is an HMAC value, not the password and not the
        # stored password hash.
        "cv": (
            credential_fingerprint
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
) -> ReauthenticationClaims:
    """
    Decode and validate a sensitive-action reauthentication
    JWT.

    Unlike decode_access_token(), this decoder returns a
    typed claims object because password-change validation
    needs both:

        user identity
        credential fingerprint
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
                    "cv",
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

    user_id = (
        _decode_subject(
            payload
        )
    )

    token_id = (
        _decode_jti(
            payload
        )
    )

    credential_fingerprint = (
        payload.get(
            "cv"
        )
    )

    if (
        not isinstance(
            credential_fingerprint,
            str,
        )
        or len(
            credential_fingerprint
        )
        != 64
    ):
        raise TokenValidationError(
            "The reauthentication "
            "credential fingerprint "
            "is invalid."
        )

    return ReauthenticationClaims(
        user_id=(
            user_id
        ),
        token_id=(
            token_id
        ),
        credential_fingerprint=(
            credential_fingerprint
        ),
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
    Calculate the CSRF-token signature for one persistent
    authentication session.
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
    Create a signed CSRF token bound to one persistent
    authentication session.
    """

    nonce = (
        secrets.token_urlsafe(
            32
        )
    )

    signature = (
        _csrf_signature(
            session_id=(
                session_id
            ),
            nonce=(
                nonce
            ),
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
    Validate a CSRF token against its persistent session ID.
    """

    (
        nonce,
        separator,
        supplied_signature,
    ) = csrf_token.partition(
        "."
    )

    if (
        not separator
        or not nonce
        or not supplied_signature
    ):
        return False

    expected_signature = (
        _csrf_signature(
            session_id=(
                session_id
            ),
            nonce=(
                nonce
            ),
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
    """
    Extract and validate a UUID-valued JWT subject claim.
    """

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


def _decode_jti(
    payload: dict,
) -> UUID:
    """
    Extract and validate the UUID-valued JWT ID claim.

    Returns the UUID for callers that need the actual token
    identifier.
    """

    token_value = (
        payload.get(
            "jti"
        )
    )

    if not isinstance(
        token_value,
        str,
    ):
        raise TokenValidationError(
            "The token identifier is invalid."
        )

    try:
        return UUID(
            token_value
        )

    except ValueError as exc:
        raise TokenValidationError(
            "The token identifier is invalid."
        ) from exc


def _validate_jti(
    payload: dict,
) -> None:
    """
    Validate a JWT ID when the caller does not need the
    parsed UUID value.
    """

    _decode_jti(
        payload
    )