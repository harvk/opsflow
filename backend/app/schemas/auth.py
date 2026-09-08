from typing import (
    Annotated,
    Literal,
)

from pydantic import (
    BaseModel,
    Field,
    SecretStr,
)

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
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
        min_length=(
            PASSWORD_MIN_LENGTH
        ),
        max_length=(
            PASSWORD_MAX_LENGTH
        ),
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

        recent reauthentication proof
        replacement password

    SecretStr prevents normal Pydantic repr/debug output from
    displaying either sensitive value.
    """

    reauth_token: SecretStr

    new_password: NewPassword


# =========================================================
# PASSWORD RESET REQUEST
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


# =========================================================
# PASSWORD RESET CREDENTIAL
# =========================================================


ResetToken = Annotated[
    SecretStr,
    Field(
        min_length=32,
        max_length=512,
    ),
]


# =========================================================
# PASSWORD RESET CONFIRMATION
# =========================================================


class PasswordResetConfirmRequest(
    BaseModel
):
    """
    Consume an opaque password-reset credential and replace
    the account password.

    Both fields are SecretStr-backed so ordinary Pydantic
    repr/debug output does not reveal either credential.
    """

    token: ResetToken

    new_password: NewPassword