from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
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
# REAUTHENTICATION
# =========================================================


class ReauthenticationRequest(
    BaseModel
):
    password: SecretStr


class ReauthenticationResponse(
    BaseModel
):
    reauth_token: str

    token_type: Literal[
        "reauth"
    ] = "reauth"

    expires_in_seconds: int


# =========================================================
# PASSWORD CHANGE
# =========================================================


NewPassword = Annotated[
    SecretStr,
    Field(
        min_length=15,
        max_length=128,
    ),
]


class PasswordChangeRequest(
    BaseModel
):
    """
    Password changes require both:

        - recent reauthentication proof
        - a replacement password

    SecretStr prevents normal Pydantic repr/debug output from
    displaying either sensitive value.
    """

    reauth_token: SecretStr

    new_password: NewPassword