from fastapi import (
    Request,
    Response,
)

from app.core.config import settings


SECONDS_PER_DAY = (
    24 * 60 * 60
)


def get_refresh_cookie(
    request: Request,
) -> str | None:
    token = request.cookies.get(
        settings.refresh_cookie_name
    )

    if not token:
        return None

    return token


def set_refresh_cookie(
    response: Response,
    token: str,
) -> None:
    response.set_cookie(
        key=(
            settings
            .refresh_cookie_name
        ),
        value=token,

        # JavaScript cannot access this cookie.
        httponly=True,

        # HTTPS-only in production.
        secure=(
            settings.is_production
        ),

        # Helps mitigate cross-site request abuse.
        samesite=(
            settings
            .refresh_cookie_samesite
        ),

        # Only auth endpoints receive this cookie.
        path=(
            settings
            .refresh_cookie_path
        ),

        max_age=(
            settings
            .refresh_token_expire_days
            * SECONDS_PER_DAY
        ),
    )


def clear_refresh_cookie(
    response: Response,
) -> None:
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
            settings.is_production
        ),
        httponly=True,
        samesite=(
            settings
            .refresh_cookie_samesite
        ),
    )


def prevent_auth_response_caching(
    response: Response,
) -> None:
    response.headers[
        "Cache-Control"
    ] = (
        "no-store, "
        "no-cache, "
        "must-revalidate"
    )

    response.headers[
        "Pragma"
    ] = "no-cache"