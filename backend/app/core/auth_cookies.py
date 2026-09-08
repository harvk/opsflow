from fastapi import (
    Request,
    Response,
)

from datetime import (
    datetime,
    timezone,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    decode_refresh_token,
)


SECONDS_PER_DAY = (
    24 * 60 * 60
)


# =========================================================
# REFRESH COOKIE
# =========================================================


def get_refresh_cookie(
    request: Request,
) -> str | None:
    """
    Read the HttpOnly refresh credential from the request.

    Empty cookie values are treated as absent credentials.
    """

    token = (
        request.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    if not token:
        return None

    return token


def _refresh_cookie_max_age(
    token: str,
) -> int:
    """
    Derive the browser cookie lifetime from the refresh
    JWT's actual absolute expiration.

    Refresh-token rotation must never extend the persistent
    authentication session.

    Therefore the cookie must expire no later than the JWT
    it contains.
    """

    claims = (
        decode_refresh_token(
            token
        )
    )

    now = datetime.now(
        timezone.utc
    )

    remaining_seconds = int(
        (
            claims.expires_at
            - now
        ).total_seconds()
    )

    return max(
        0,
        remaining_seconds,
    )


def set_refresh_cookie(
    response: Response,
    token: str,
) -> None:
    """
    Store the refresh JWT as an HttpOnly browser cookie.

    The cookie lifetime is derived from the JWT's own
    absolute expiration.

    This is critical during refresh-token rotation because
    rotation changes the token ID but does NOT extend the
    persistent authentication session.
    """

    max_age = (
        _refresh_cookie_max_age(
            token
        )
    )

    response.set_cookie(
        key=(
            settings
            .refresh_cookie_name
        ),
        value=token,
        httponly=True,
        secure=(
            settings
            .is_production
        ),
        samesite=(
            settings
            .refresh_cookie_samesite
        ),
        path=(
            settings
            .refresh_cookie_path
        ),
        max_age=(
            max_age
        ),
    )


def clear_refresh_cookie(
    response: Response,
) -> None:
    """
    Expire the refresh credential.

    Cookie deletion deliberately mirrors the attributes
    used when the cookie was created.
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
# CSRF COOKIE
# =========================================================


def get_csrf_cookie(
    request: Request,
) -> str | None:
    """
    Read the browser CSRF proof.

    Unlike the refresh JWT, this value is intentionally
    readable by frontend JavaScript.
    """

    token = (
        request.cookies.get(
            settings
            .csrf_cookie_name
        )
    )

    if not token:
        return None

    return token


def set_csrf_cookie(
    response: Response,
    token: str,
) -> None:
    """
    Store the signed CSRF proof.

    HttpOnly must remain False because the frontend copies
    this value into the configured CSRF request header.

    The CSRF cookie is not an authentication credential.
    """

    response.set_cookie(
        key=(
            settings
            .csrf_cookie_name
        ),
        value=token,
        httponly=False,
        secure=(
            settings
            .is_production
        ),
        samesite=(
            settings
            .refresh_cookie_samesite
        ),

        # The SPA must be able to read this cookie while
        # operating outside /api/v1/auth.
        path="/",
    )


def clear_csrf_cookie(
    response: Response,
) -> None:
    """
    Expire the CSRF cookie using the same security
    attributes with which it was created.
    """

    response.delete_cookie(
        key=(
            settings
            .csrf_cookie_name
        ),
        path="/",
        secure=(
            settings
            .is_production
        ),
        httponly=False,
        samesite=(
            settings
            .refresh_cookie_samesite
        ),
    )


# =========================================================
# COMPLETE BROWSER AUTH STATE
# =========================================================


def clear_auth_cookies(
    response: Response,
) -> None:
    """
    Remove all browser-managed authentication state.

    The access token is deliberately not handled here
    because it exists only in frontend memory.
    """

    clear_refresh_cookie(
        response
    )

    clear_csrf_cookie(
        response
    )