"""
Stable public-facing authentication response messages.

These constants form the HTTP disclosure boundary between
the authentication domain and untrusted clients.

Domain/service exceptions may contain more specific
diagnostic information. Routes must not expose those
exception strings directly.

Security telemetry should carry internal reason codes
separately from these public messages.
"""


# =========================================================
# ACCESS AUTHENTICATION
# =========================================================


ACCESS_CREDENTIALS_INVALID_MESSAGE = (
    "Could not validate credentials."
)


LOGIN_CREDENTIALS_INVALID_MESSAGE = (
    "Incorrect email or password."
)


LOGIN_THROTTLED_MESSAGE = (
    "Too many authentication attempts. "
    "Please try again later."
)


# =========================================================
# REFRESH AUTHENTICATION
# =========================================================


REFRESH_CREDENTIALS_INVALID_MESSAGE = (
    "Could not refresh credentials."
)


CSRF_VALIDATION_FAILED_MESSAGE = (
    "CSRF validation failed."
)


# =========================================================
# REAUTHENTICATION
# =========================================================


REAUTHENTICATION_FAILED_MESSAGE = (
    "Reauthentication failed."
)


REAUTHENTICATION_REQUIRED_MESSAGE = (
    "Valid recent reauthentication is required."
)


# =========================================================
# PASSWORD CHANGE
# =========================================================


PASSWORD_CHANGE_REJECTED_MESSAGE = (
    "The new password could not be accepted."
)


# =========================================================
# PASSWORD RESET
# =========================================================


PASSWORD_RESET_THROTTLED_MESSAGE = (
    "Too many password reset requests. "
    "Please try again later."
)


PASSWORD_RESET_CREDENTIAL_INVALID_MESSAGE = (
    "The password reset credential is invalid or expired."
)


PASSWORD_RESET_PASSWORD_REJECTED_MESSAGE = (
    "The new password could not be accepted."
)