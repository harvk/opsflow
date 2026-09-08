from __future__ import annotations


# =========================================================
# PASSWORD LENGTH POLICY
# =========================================================
#
# OpsFlow currently treats passwords as a single
# authentication factor.
#
# The policy intentionally uses length boundaries rather
# than composition requirements.
#
# Python len(str) measures Unicode code points for ordinary
# password input, matching the behavior previously embedded
# independently inside:
#
#     AuthenticationService
#     PasswordResetService
#
# Keeping these values here establishes one canonical
# server-side source of truth.
# =========================================================


PASSWORD_MIN_LENGTH = 15

PASSWORD_MAX_LENGTH = 128


# =========================================================
# PUBLIC POLICY MESSAGES
# =========================================================
#
# These messages deliberately preserve the wording already
# used by the authentication and recovery services.
#
# Keeping the messages centralized prevents the two flows
# from drifting independently.
# =========================================================


PASSWORD_TOO_SHORT_MESSAGE = (
    "The new password must contain "
    f"at least {PASSWORD_MIN_LENGTH} characters."
)

PASSWORD_TOO_LONG_MESSAGE = (
    "The new password must not exceed "
    f"{PASSWORD_MAX_LENGTH} characters."
)


# =========================================================
# POLICY ERROR
# =========================================================


class PasswordPolicyViolation(
    ValueError
):
    """
    Raised when a proposed replacement password violates the
    shared OpsFlow server-side password policy.

    This exception belongs to the core policy layer.

    Higher application layers should translate it into their
    own domain-specific error type.

    For example:

        AuthenticationService
            -> PasswordChangeError

        PasswordResetService
            -> PasswordResetPasswordError

    That separation keeps the core policy reusable without
    coupling it to a particular authentication workflow.
    """

    pass


# =========================================================
# POLICY VALIDATION
# =========================================================


def validate_new_password(
    password: str,
) -> None:
    """
    Validate a proposed replacement password.

    Current OpsFlow policy:

        minimum:
            15 Unicode code points

        maximum:
            128 Unicode code points

        composition rules:
            none

    Successful validation returns None.

    This function does NOT determine whether the new
    password equals the user's current password.

    Password reuse requires access to the stored credential
    hash and therefore remains the responsibility of the
    authentication or password-recovery service.
    """

    password_length = (
        len(
            password
        )
    )

    if (
        password_length
        < PASSWORD_MIN_LENGTH
    ):
        raise PasswordPolicyViolation(
            PASSWORD_TOO_SHORT_MESSAGE
        )

    if (
        password_length
        > PASSWORD_MAX_LENGTH
    ):
        raise PasswordPolicyViolation(
            PASSWORD_TOO_LONG_MESSAGE
        )