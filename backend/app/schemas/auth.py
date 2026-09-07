from typing import (
    Annotated,
    Literal,
)

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
# SHARED REPLACEMENT PASSWORD TYPE
# =========================================================


NewPassword = Annotated[
    SecretStr,
    Field(
        min_length=15,
        max_length=128,
    ),
]


# =========================================================
# PASSWORD CHANGE
# =========================================================


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


# =========================================================
# PASSWORD RESET
# =========================================================


class PasswordResetRequest(
    BaseModel
):
    """
    Begin anonymous account recovery.

    The HTTP layer always returns the same externally visible
    response regardless of whether this email identifies an
    eligible account.
    """

    email: Annotated[
        str,
        Field(
            min_length=3,
            max_length=320,
        ),
    ]


class PasswordResetRequestResponse(
    BaseModel
):
    """
    Enumeration-resistant reset-request response.
    """

    message: str


ResetToken = Annotated[
    SecretStr,
    Field(
        min_length=32,
        max_length=512,
    ),
]


class PasswordResetConfirmRequest(
    BaseModel
):
    """
    Consume an opaque password-reset credential and replace
    the account password.

    Neither sensitive field is rendered as plaintext through
    ordinary Pydantic repr/debug output.
    """

    token: ResetToken

    new_password: NewPassword