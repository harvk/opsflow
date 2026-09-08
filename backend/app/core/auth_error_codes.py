from __future__ import annotations

from collections.abc import (
    Mapping,
)

from enum import (
    StrEnum,
)


AUTH_ERROR_CODE_HEADER = (
    "X-Auth-Error-Code"
)


class AuthErrorCode(
    StrEnum
):
    """
    Stable machine-readable authentication error codes.

    These values are part of the public HTTP contract.

    Human-readable response messages may be revised for
    clarity, but these identifiers should remain stable so
    frontend clients never need to infer authentication
    state from prose.
    """

    ACCESS_CREDENTIALS_INVALID = (
        "AUTH_ACCESS_CREDENTIALS_INVALID"
    )

    LOGIN_CREDENTIALS_INVALID = (
        "AUTH_LOGIN_CREDENTIALS_INVALID"
    )

    LOGIN_THROTTLED = (
        "AUTH_LOGIN_THROTTLED"
    )

    REFRESH_CREDENTIALS_INVALID = (
        "AUTH_REFRESH_CREDENTIALS_INVALID"
    )

    CSRF_VALIDATION_FAILED = (
        "AUTH_CSRF_VALIDATION_FAILED"
    )

    REAUTHENTICATION_FAILED = (
        "AUTH_REAUTHENTICATION_FAILED"
    )

    REAUTHENTICATION_REQUIRED = (
        "AUTH_REAUTHENTICATION_REQUIRED"
    )

    PASSWORD_CHANGE_REJECTED = (
        "AUTH_PASSWORD_CHANGE_REJECTED"
    )

    PASSWORD_RESET_THROTTLED = (
        "AUTH_PASSWORD_RESET_THROTTLED"
    )

    PASSWORD_RESET_CREDENTIAL_INVALID = (
        "AUTH_PASSWORD_RESET_CREDENTIAL_INVALID"
    )

    PASSWORD_RESET_PASSWORD_REJECTED = (
        "AUTH_PASSWORD_RESET_PASSWORD_REJECTED"
    )


def auth_error_headers(
    code: AuthErrorCode,
    *,
    additional_headers: (
        Mapping[
            str,
            str,
        ]
        | None
    ) = None,
) -> dict[
    str,
    str,
]:
    """
    Construct HTTP headers for an authentication failure.

    Functional protocol headers such as:

        WWW-Authenticate
        Retry-After

    may be supplied by the route and are preserved.

    The authentication error code is added last so callers
    cannot accidentally override the public error contract.
    """

    headers: dict[
        str,
        str,
    ] = {}

    if additional_headers:
        headers.update(
            additional_headers
        )

    headers[
        AUTH_ERROR_CODE_HEADER
    ] = (
        code.value
    )

    return headers