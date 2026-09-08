from fastapi import (
    Request,
    Response,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from uuid import (
    uuid4,
)

from app.core.security import (
    create_refresh_token,
)

from app.core.auth_cookies import (
    clear_auth_cookies,
    clear_csrf_cookie,
    clear_refresh_cookie,
    get_csrf_cookie,
    get_refresh_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)

from app.core.config import (
    settings,
)


# =========================================================
# REQUEST HELPER
# =========================================================


def create_request(
    *,
    cookie_header: str | None = None,
) -> Request:
    headers: list[
        tuple[
            bytes,
            bytes,
        ]
    ] = []

    if cookie_header is not None:
        headers.append(
            (
                b"cookie",
                cookie_header.encode(
                    "utf-8"
                ),
            )
        )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": b"",
        "server": (
            "testserver",
            80,
        ),
        "client": (
            "127.0.0.1",
            12345,
        ),
        "scheme": "http",
    }

    return Request(
        scope
    )
    
    
# =========================================================
# COOKIE HELPER
# =========================================================
    
    
def create_refresh_token_for_cookie_test(
) -> str:
    return (
        create_refresh_token(
            uuid4(),
            session_id=(
                uuid4()
            ),
            token_id=(
                uuid4()
            ),
            expires_at=(
                datetime.now(
                    timezone.utc
                )
                + timedelta(
                    hours=1
                )
            ),
        )
    )


# =========================================================
# REFRESH COOKIE READING
# =========================================================


def test_get_refresh_cookie_returns_value(
) -> None:
    request = create_request(
        cookie_header=(
            f"{settings.refresh_cookie_name}"
            "=refresh-value"
        )
    )

    assert (
        get_refresh_cookie(
            request
        )
        == "refresh-value"
    )


def test_get_refresh_cookie_returns_none_when_missing(
) -> None:
    request = create_request()

    assert (
        get_refresh_cookie(
            request
        )
        is None
    )


def test_get_refresh_cookie_treats_empty_value_as_missing(
) -> None:
    request = create_request(
        cookie_header=(
            f"{settings.refresh_cookie_name}="
        )
    )

    assert (
        get_refresh_cookie(
            request
        )
        is None
    )


# =========================================================
# CSRF COOKIE READING
# =========================================================


def test_get_csrf_cookie_returns_value(
) -> None:
    request = create_request(
        cookie_header=(
            f"{settings.csrf_cookie_name}"
            "=csrf-value"
        )
    )

    assert (
        get_csrf_cookie(
            request
        )
        == "csrf-value"
    )


def test_get_csrf_cookie_returns_none_when_missing(
) -> None:
    request = create_request()

    assert (
        get_csrf_cookie(
            request
        )
        is None
    )


# =========================================================
# REFRESH COOKIE WRITING
# =========================================================


def test_set_refresh_cookie_is_httponly(
) -> None:
    token = (
        create_refresh_token_for_cookie_test()
    )

    response = Response()

    set_refresh_cookie(
        response,
        token,
    )

    header = (
        response.headers[
            "set-cookie"
        ]
        .lower()
    )

    assert (
        "httponly"
        in header
    )


def test_set_refresh_cookie_uses_configured_path(
) -> None:
    token = (
        create_refresh_token_for_cookie_test()
    )

    response = Response()

    set_refresh_cookie(
        response,
        token,
    )

    header = (
        response.headers[
            "set-cookie"
        ]
    )

    assert (
        f"Path={settings.refresh_cookie_path}"
        in header
    )


def test_set_refresh_cookie_uses_refresh_jwt_remaining_lifetime(
) -> None:
    expires_in_seconds = (
        60 * 60
    )

    expires_at = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            seconds=(
                expires_in_seconds
            )
        )
    )

    token = (
        create_refresh_token(
            uuid4(),
            session_id=(
                uuid4()
            ),
            token_id=(
                uuid4()
            ),
            expires_at=(
                expires_at
            ),
        )
    )

    response = Response()

    set_refresh_cookie(
        response,
        token,
    )

    header = (
        response.headers[
            "set-cookie"
        ]
    )

    max_age_part = next(
        part
        for part in (
            header.split(
                ";"
            )
        )
        if (
            part
            .strip()
            .lower()
            .startswith(
                "max-age="
            )
        )
    )

    max_age = int(
        max_age_part
        .strip()
        .split(
            "=",
            1,
        )[1]
    )

    # It must never receive the application's complete
    # configured refresh lifetime merely because the token
    # was rotated.
    assert (
        max_age
        <= expires_in_seconds
    )

    # Allow a few seconds for test execution.
    assert (
        max_age
        >= (
            expires_in_seconds
            - 5
        )
    )


# =========================================================
# CSRF COOKIE WRITING
# =========================================================


def test_set_csrf_cookie_is_not_httponly(
) -> None:
    response = Response()

    set_csrf_cookie(
        response,
        "csrf-value",
    )

    header = (
        response.headers[
            "set-cookie"
        ]
        .lower()
    )

    assert (
        "httponly"
        not in header
    )


def test_set_csrf_cookie_uses_root_path(
) -> None:
    response = Response()

    set_csrf_cookie(
        response,
        "csrf-value",
    )

    header = (
        response.headers[
            "set-cookie"
        ]
    )

    assert (
        "Path=/"
        in header
    )


# =========================================================
# COOKIE DELETION
# =========================================================


def test_clear_refresh_cookie_expires_refresh_cookie(
) -> None:
    response = Response()

    clear_refresh_cookie(
        response
    )

    header = (
        response.headers[
            "set-cookie"
        ]
    )

    assert (
        settings
        .refresh_cookie_name
        in header
    )

    assert (
        "Max-Age=0"
        in header
    )


def test_clear_csrf_cookie_expires_csrf_cookie(
) -> None:
    response = Response()

    clear_csrf_cookie(
        response
    )

    header = (
        response.headers[
            "set-cookie"
        ]
    )

    assert (
        settings
        .csrf_cookie_name
        in header
    )

    assert (
        "Max-Age=0"
        in header
    )


def test_clear_auth_cookies_expires_both_cookies(
) -> None:
    response = Response()

    clear_auth_cookies(
        response
    )

    headers = (
        response.headers.getlist(
            "set-cookie"
        )
    )

    assert (
        len(
            headers
        )
        == 2
    )

    combined = (
        "\n".join(
            headers
        )
    )

    assert (
        settings
        .refresh_cookie_name
        in combined
    )

    assert (
        settings
        .csrf_cookie_name
        in combined
    )