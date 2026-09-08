from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    Request,
    Response,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    decode_refresh_token,
)


# =========================================================
# REFRESH COOKIE READ
# =========================================================


def get_refresh_cookie(
    request: Request,
) -> str | None:
    """
    Read the browser's HttpOnly refresh credential.

    The cookie value itself is returned only to the
    authentication boundary and must never be logged.
    """

    token = (
        request.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    if not token:
        return (
            None
        )

    return (
        token
    )


# =========================================================
# REFRESH COOKIE ABSOLUTE LIFETIME
# =========================================================


def _get_refresh_cookie_lifetime(
    token: str,
) -> tuple[
    int,
    datetime,
]:
    """
    Derive the browser-cookie lifetime directly from the
    signed refresh JWT's absolute expiration.

    This prevents cookie rotation from creating a sliding
    browser lifetime.

    Example:

        persistent session expires at 15:00
        refresh JWT expires at       15:00

        refresh performed at         14:55

    The replacement cookie receives approximately five
    minutes of Max-Age, NOT another full configured refresh
    lifetime.

    decode_refresh_token() also verifies that the value being
    placed into the privileged refresh cookie is actually a
    valid refresh JWT issued under the application's refresh
    credential contract.
    """

    claims = (
        decode_refresh_token(
            token
        )
    )

    expires_at = (
        claims
        .expires_at
        .astimezone(
            timezone.utc
        )
    )

    now = (
        datetime.now(
            timezone.utc
        )
    )

    remaining_seconds = (
        int(
            (
                expires_at
                - now
            )
            .total_seconds()
        )
    )

    # Never emit a negative Max-Age.
    #
    # A zero value instructs the browser not to persist a
    # credential that has no usable lifetime remaining.

    if (
        remaining_seconds
        < 0
    ):
        remaining_seconds = (
            0
        )

    return (
        remaining_seconds,
        expires_at,
    )


# =========================================================
# REFRESH COOKIE WRITE
# =========================================================


def set_refresh_cookie(
    response: Response,
    token: str,
) -> None:
    """
    Store a refresh JWT in the browser.

    Browser persistence is bounded by the refresh token's
    existing absolute expiration.

    IMPORTANT:

    This helper must never recalculate a fresh lifetime from:

        settings.refresh_token_expire_days

    during refresh rotation.

    Doing so would create a sliding cookie lifetime even
    though the persistent session and refresh JWT retain an
    absolute expiration.
    """

    (
        max_age,
        expires_at,
    ) = (
        _get_refresh_cookie_lifetime(
            token
        )
    )

    response.set_cookie(
        key=(
            settings
            .refresh_cookie_name
        ),
        value=(
            token
        ),

        # JavaScript cannot access this credential.
        httponly=True,

        # HTTPS-only in production.
        secure=(
            settings
            .is_production
        ),

        # Helps mitigate cross-site request abuse.
        samesite=(
            settings
            .refresh_cookie_samesite
        ),

        # Only configured authentication endpoints receive
        # the refresh credential.
        path=(
            settings
            .refresh_cookie_path
        ),

        # Relative browser lifetime.
        #
        # This represents only the time remaining until the
        # JWT's already-established absolute expiration.
        max_age=(
            max_age
        ),

        # Absolute browser lifetime.
        #
        # Providing Expires as well as Max-Age makes the same
        # absolute boundary explicit in the Set-Cookie
        # header.
        expires=(
            expires_at
        ),
    )


# =========================================================
# REFRESH COOKIE CLEAR
# =========================================================


def clear_refresh_cookie(
    response: Response,
) -> None:
    """
    Explicitly remove the browser refresh credential.

    Cookie deletion must use the same path and security
    attributes as cookie creation so the browser targets the
    correct cookie.
    """

    response.delete_cookie(
        key=(
            settings
            .refresh_cookie_name
        ),
        path=(
            settings
            .refresh_cookie_path
        ),
        secure=(
            settings
            .is_production
        ),
        httponly=True,
        samesite=(
            settings
            .refresh_cookie_samesite
        ),
    )


# =========================================================
# AUTH RESPONSE CACHE CONTROL
# =========================================================


def prevent_auth_response_caching(
    response: Response,
) -> None:
    """
    Prevent authentication responses from being retained by
    browser/intermediary caches.
    """

    response.headers[
        "Cache-Control"
    ] = (
        "no-store, "
        "no-cache, "
        "must-revalidate"
    )

    response.headers[
        "Pragma"
    ] = (
        "no-cache"
    )