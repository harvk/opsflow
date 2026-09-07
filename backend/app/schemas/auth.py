from typing import (
    Literal,
)

from pydantic import (
    BaseModel,
    SecretStr,
)


# =========================================================
# ORDINARY AUTHENTICATION
# =========================================================


class TokenResponse(
    BaseModel
):
    access_token: str

    token_type: Literal[
        "bearer"
    ] = "bearer"


# =========================================================
# SENSITIVE-ACTION REAUTHENTICATION
# =========================================================


class ReauthenticationRequest(
    BaseModel
):
    """
    Current password supplied by an already-authenticated
    user.

    SecretStr prevents ordinary Pydantic representations from
    displaying the clear-text password.
    """

    password: SecretStr


class ReauthenticationResponse(
    BaseModel
):
    """
    Short-lived proof of recent password verification.

    This credential should remain in frontend memory only.
    """

    reauth_token: str

    token_type: Literal[
        "reauth"
    ] = "reauth"

    expires_in_seconds: int