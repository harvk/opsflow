from __future__ import annotations

import hashlib
import hmac
import secrets


# =========================================================
# PASSWORD RESET TOKEN CONFIGURATION
# =========================================================

PASSWORD_RESET_TOKEN_BYTES = 48


# =========================================================
# RAW TOKEN GENERATION
# =========================================================


def generate_password_reset_token() -> str:
    """
    Generate a cryptographically random opaque credential
    for password recovery.

    The returned value is the credential that will
    eventually be delivered to the account owner through a
    side channel such as email.

    The raw value must NEVER be persisted in the database.
    """

    return secrets.token_urlsafe(
        PASSWORD_RESET_TOKEN_BYTES
    )


# =========================================================
# TOKEN DIGEST
# =========================================================


def digest_password_reset_token(
    token: str,
) -> str:
    """
    Convert the raw password-reset token into the value
    stored by the database.

    Password-reset tokens contain high cryptographic entropy,
    so SHA-256 is appropriate for lookup storage.

    This is intentionally different from user passwords,
    which must use the application's slow password-hashing
    algorithm.
    """

    if not token:
        raise ValueError(
            "Password-reset token cannot be empty."
        )

    return hashlib.sha256(
        token.encode(
            "utf-8"
        )
    ).hexdigest()


# =========================================================
# CREDENTIAL VERSION BINDING
# =========================================================


def create_password_reset_credential_fingerprint(
    hashed_password: str,
) -> str:
    """
    Bind a reset token to the password hash that existed at
    the time the token was issued.

    If the user's password changes before this reset token is
    consumed, the stored fingerprint will no longer match.

    The password hash itself is never stored in the reset
    token row.
    """

    if not hashed_password:
        raise ValueError(
            "Password hash cannot be empty."
        )

    message = (
        "opsflow-password-reset-credential:"
        f"{hashed_password}"
    )

    return hashlib.sha256(
        message.encode(
            "utf-8"
        )
    ).hexdigest()


def password_reset_credential_matches(
    *,
    hashed_password: str,
    credential_fingerprint: str,
) -> bool:
    """
    Determine whether a reset credential still belongs to
    the user's current stored password version.
    """

    expected_fingerprint = (
        create_password_reset_credential_fingerprint(
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