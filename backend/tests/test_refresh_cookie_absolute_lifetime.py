from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from email.utils import (
    parsedate_to_datetime,
)

from http.cookies import (
    SimpleCookie,
)

from typing import (
    Any,
)

from uuid import (
    uuid4,
)

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy import (
    text,
)

from sqlalchemy.orm import (
    Session,
)

from app.api.dependencies import (
    get_login_throttle,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    decode_refresh_token,
)

from app.domain.user import (
    User,
    UserRole,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# TEST CREDENTIAL
# =========================================================


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# COOKIE EXPIRATION TOLERANCE
# =========================================================
#
# HTTP cookie Max-Age begins when the browser receives the
# response, while the JWT exp was calculated slightly
# earlier during request processing.
#
# A small tolerance avoids treating normal sub-second /
# short request-processing differences as policy drift.
#
# It is deliberately tiny compared with the multi-day
# refresh lifetime.
# =========================================================


COOKIE_EXPIRATION_TOLERANCE = (
    timedelta(
        seconds=5
    )
)


# =========================================================
# COOKIE SNAPSHOT
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class RefreshCookieSnapshot:
    value: str

    max_age: int | None

    expires: datetime | None

    path: str | None

    httponly: bool

    secure: bool

    samesite: str | None


# =========================================================
# USER FACTORY
# =========================================================


def create_refresh_cookie_user(
    db_session: Session,
) -> User:
    """
    Create one isolated active account.

    Unique email addresses also prevent account-level login
    throttle state from leaking between test cases.
    """

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = (
        UserService(
            repository
        )
    )

    user = (
        service.create_user(
            email=(
                "refresh-cookie-lifetime-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Refresh Cookie Lifetime User"
            ),
            password=(
                TEST_PASSWORD
            ),
            role=(
                UserRole.OPERATOR
            ),
        )
    )

    db_session.flush()

    return (
        user
    )


# =========================================================
# SET-COOKIE EXTRACTION
# =========================================================


def require_refresh_cookie_from_response(
    response: Any,
) -> RefreshCookieSnapshot:
    """
    Locate the refresh-token Set-Cookie header emitted by
    FastAPI and parse its browser lifetime/security
    attributes.

    There may be multiple Set-Cookie headers because login
    also establishes the CSRF cookie.
    """

    set_cookie_headers = (
        response.headers.get_list(
            "set-cookie"
        )
    )

    assert (
        set_cookie_headers
    ), (
        "Expected the response to contain at least one "
        "Set-Cookie header."
    )

    for header in (
        set_cookie_headers
    ):
        cookie = (
            SimpleCookie()
        )

        cookie.load(
            header
        )

        if (
            settings
            .refresh_cookie_name
            not in cookie
        ):
            continue

        morsel = (
            cookie[
                settings
                .refresh_cookie_name
            ]
        )

        raw_max_age = (
            morsel[
                "max-age"
            ]
        )

        max_age: (
            int | None
        ) = (
            int(
                raw_max_age
            )
            if raw_max_age
            else None
        )

        raw_expires = (
            morsel[
                "expires"
            ]
        )

        expires: (
            datetime | None
        ) = None

        if (
            raw_expires
        ):
            expires = (
                parsedate_to_datetime(
                    raw_expires
                )
            )

            if (
                expires.tzinfo
                is None
            ):
                expires = (
                    expires.replace(
                        tzinfo=(
                            timezone.utc
                        )
                    )
                )

            expires = (
                expires.astimezone(
                    timezone.utc
                )
            )

        raw_path = (
            morsel[
                "path"
            ]
        )

        raw_samesite = (
            morsel[
                "samesite"
            ]
        )

        return (
            RefreshCookieSnapshot(
                value=(
                    morsel.value
                ),
                max_age=(
                    max_age
                ),
                expires=(
                    expires
                ),
                path=(
                    raw_path
                    or None
                ),
                httponly=(
                    bool(
                        morsel[
                            "httponly"
                        ]
                    )
                ),
                secure=(
                    bool(
                        morsel[
                            "secure"
                        ]
                    )
                ),
                samesite=(
                    raw_samesite.lower()
                    if raw_samesite
                    else None
                ),
            )
        )

    raise AssertionError(
        "The response did not contain a Set-Cookie header "
        f"for {settings.refresh_cookie_name!r}."
    )


# =========================================================
# CLIENT COOKIE HELPER
# =========================================================


def require_client_cookie(
    client: TestClient,
    *,
    cookie_name: str,
) -> str:
    value = (
        client.cookies.get(
            cookie_name
        )
    )

    assert (
        value
        is not None
    ), (
        f"Expected browser cookie "
        f"{cookie_name!r}."
    )

    assert (
        value
        != ""
    )

    return (
        value
    )


# =========================================================
# LOGIN HELPER
# =========================================================


def login(
    client: TestClient,
    *,
    user: User,
):
    """
    Establish a real browser authentication session and
    return the HTTP login response.
    """

    get_login_throttle.cache_clear()

    try:
        response = (
            client.post(
                "/api/v1/auth/token",
                data={
                    "username": (
                        user.email
                    ),
                    "password": (
                        TEST_PASSWORD
                    ),
                },
            )
        )

        assert (
            response.status_code
            == 200
        ), response.text

        return (
            response
        )

    finally:
        get_login_throttle.cache_clear()


# =========================================================
# COOKIE/JWT EXPIRATION CONTRACT
# =========================================================


def assert_cookie_does_not_outlive_refresh_token(
    *,
    cookie: RefreshCookieSnapshot,
    response_received_at: datetime,
) -> None:
    """
    Assert that browser persistence cannot extend beyond the
    credential's absolute JWT expiration.

    A persistent refresh cookie must provide Max-Age,
    Expires, or both.

    Every supplied lifetime mechanism must remain bounded by
    the refresh token's absolute expiration.
    """

    claims = (
        decode_refresh_token(
            cookie.value
        )
    )

    token_expires_at = (
        claims
        .expires_at
        .astimezone(
            timezone.utc
        )
    )

    has_browser_expiration = (
        cookie.max_age
        is not None
        or cookie.expires
        is not None
    )

    assert (
        has_browser_expiration
    ), (
        "The refresh credential was emitted as a browser "
        "session cookie without Max-Age or Expires. "
        "Its browser lifetime is therefore not explicitly "
        "bounded to the refresh session's absolute "
        "expiration."
    )

    if (
        cookie.max_age
        is not None
    ):
        assert (
            cookie.max_age
            >= 0
        )

        max_age_expiration = (
            response_received_at
            + timedelta(
                seconds=(
                    cookie.max_age
                )
            )
        )

        assert (
            max_age_expiration
            <= (
                token_expires_at
                + COOKIE_EXPIRATION_TOLERANCE
            )
        ), (
            "Refresh-cookie Max-Age outlives the refresh "
            "JWT's absolute expiration. "
            f"Cookie expiration≈{max_age_expiration!s}, "
            f"JWT expiration={token_expires_at!s}."
        )

    if (
        cookie.expires
        is not None
    ):
        assert (
            cookie.expires
            <= (
                token_expires_at
                + COOKIE_EXPIRATION_TOLERANCE
            )
        ), (
            "Refresh-cookie Expires outlives the refresh "
            "JWT's absolute expiration. "
            f"Cookie expiration={cookie.expires!s}, "
            f"JWT expiration={token_expires_at!s}."
        )


# =========================================================
# INITIAL LOGIN COOKIE LIFETIME
# =========================================================


def test_login_refresh_cookie_does_not_outlive_initial_refresh_token(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Initial authentication must align:

        persistent session expiration
        refresh JWT expiration
        browser refresh-cookie expiration
    """

    user = (
        create_refresh_cookie_user(
            db_session
        )
    )

    response = (
        login(
            client,
            user=user,
        )
    )

    response_received_at = (
        datetime.now(
            timezone.utc
        )
    )

    refresh_cookie = (
        require_refresh_cookie_from_response(
            response
        )
    )

    assert_cookie_does_not_outlive_refresh_token(
        cookie=(
            refresh_cookie
        ),
        response_received_at=(
            response_received_at
        ),
    )

    claims = (
        decode_refresh_token(
            refresh_cookie.value
        )
    )

    session_expiration = (
        db_session.execute(
            text(
                """
                SELECT expires_at
                FROM auth_sessions
                WHERE id = :session_id
                """
            ),
            {
                "session_id": (
                    claims.session_id
                ),
            },
        )
        .scalar_one()
    )

    assert isinstance(
        session_expiration,
        datetime,
    )

    assert (
        int(
            session_expiration
            .timestamp()
        )
        == int(
            claims
            .expires_at
            .timestamp()
        )
    )


# =========================================================
# COOKIE SECURITY ATTRIBUTES
# =========================================================


def test_refresh_cookie_preserves_security_attributes(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Lifetime hardening must not accidentally weaken the
    existing browser credential protections.
    """

    user = (
        create_refresh_cookie_user(
            db_session
        )
    )

    response = (
        login(
            client,
            user=user,
        )
    )

    refresh_cookie = (
        require_refresh_cookie_from_response(
            response
        )
    )

    assert (
        refresh_cookie.httponly
        is True
    )

    assert (
        refresh_cookie.secure
        is settings.is_production
    )

    assert (
        refresh_cookie.samesite
        == (
            settings
            .refresh_cookie_samesite
            .lower()
        )
    )

    assert (
        refresh_cookie.path
        == settings
        .refresh_cookie_path
    )


# =========================================================
# ROTATION MUST NOT SLIDE COOKIE LIFETIME
# =========================================================


def test_refresh_rotation_cookie_uses_remaining_absolute_session_lifetime(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    This is the central 7C regression test.

    We deliberately shorten the server-side persistent
    session to only five minutes.

    The old refresh JWT remains cryptographically signed and
    originally had a much longer expiration.

    On refresh:

        the server reads the shortened auth-session lifetime
        replacement JWT exp becomes that shorter boundary
        replacement browser cookie must use only that same
        remaining lifetime

    A cookie helper that blindly resets Max-Age to another
    full configured refresh lifetime will fail this test.
    """

    user = (
        create_refresh_cookie_user(
            db_session
        )
    )

    login_response = (
        login(
            client,
            user=user,
        )
    )

    initial_cookie = (
        require_refresh_cookie_from_response(
            login_response
        )
    )

    initial_claims = (
        decode_refresh_token(
            initial_cookie.value
        )
    )

    csrf_token = (
        require_client_cookie(
            client,
            cookie_name=(
                settings
                .csrf_cookie_name
            ),
        )
    )

    # -----------------------------------------------------
    # SHORTEN THE AUTHORITATIVE SERVER SESSION
    # -----------------------------------------------------

    shortened_expiration = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=5
        )
    )

    db_session.execute(
        text(
            """
            UPDATE auth_sessions
            SET expires_at = :expires_at
            WHERE id = :session_id
            """
        ),
        {
            "expires_at": (
                shortened_expiration
            ),
            "session_id": (
                initial_claims
                .session_id
            ),
        },
    )

    db_session.flush()

    # -----------------------------------------------------
    # ROTATE THROUGH THE REAL HTTP ENDPOINT
    # -----------------------------------------------------

    response = (
        client.post(
            "/api/v1/auth/refresh",
            headers={
                settings
                .csrf_header_name: (
                    csrf_token
                ),
            },
        )
    )

    response_received_at = (
        datetime.now(
            timezone.utc
        )
    )

    assert (
        response.status_code
        == 200
    ), response.text

    replacement_cookie = (
        require_refresh_cookie_from_response(
            response
        )
    )

    replacement_claims = (
        decode_refresh_token(
            replacement_cookie.value
        )
    )

    # -----------------------------------------------------
    # SAME SESSION FAMILY
    # -----------------------------------------------------

    assert (
        replacement_claims
        .session_id
        == initial_claims
        .session_id
    )

    assert (
        replacement_claims
        .token_id
        != initial_claims
        .token_id
    )

    # -----------------------------------------------------
    # JWT NOW USES THE SHORTENED ABSOLUTE BOUNDARY
    # -----------------------------------------------------

    assert (
        abs(
            int(
                replacement_claims
                .expires_at
                .timestamp()
            )
            - int(
                shortened_expiration
                .timestamp()
            )
        )
        <= 1
    )

    # -----------------------------------------------------
    # BROWSER COOKIE CANNOT SLIDE BEYOND THAT BOUNDARY
    # -----------------------------------------------------

    assert_cookie_does_not_outlive_refresh_token(
        cookie=(
            replacement_cookie
        ),
        response_received_at=(
            response_received_at
        ),
    )

    # If Max-Age is used, it should now be approximately
    # five minutes — certainly nowhere near another full
    # multi-day refresh lifetime.

    if (
        replacement_cookie
        .max_age
        is not None
    ):
        assert (
            replacement_cookie
            .max_age
            <= 305
        ), (
            "Refresh rotation reset the browser cookie to "
            "a sliding lifetime instead of the remaining "
            "absolute session lifetime."
        )


# =========================================================
# ROTATION SECURITY ATTRIBUTES
# =========================================================


def test_rotated_refresh_cookie_keeps_security_attributes(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Reissuing the refresh credential must retain the same
    browser hardening attributes as initial login.
    """

    user = (
        create_refresh_cookie_user(
            db_session
        )
    )

    login_response = (
        login(
            client,
            user=user,
        )
    )

    initial_cookie = (
        require_refresh_cookie_from_response(
            login_response
        )
    )

    csrf_token = (
        require_client_cookie(
            client,
            cookie_name=(
                settings
                .csrf_cookie_name
            ),
        )
    )

    refresh_response = (
        client.post(
            "/api/v1/auth/refresh",
            headers={
                settings
                .csrf_header_name: (
                    csrf_token
                ),
            },
        )
    )

    assert (
        refresh_response.status_code
        == 200
    ), refresh_response.text

    rotated_cookie = (
        require_refresh_cookie_from_response(
            refresh_response
        )
    )

    assert (
        rotated_cookie.httponly
        == initial_cookie.httponly
        == True
    )

    assert (
        rotated_cookie.secure
        == initial_cookie.secure
        == settings.is_production
    )

    assert (
        rotated_cookie.samesite
        == initial_cookie.samesite
        == (
            settings
            .refresh_cookie_samesite
            .lower()
        )
    )

    assert (
        rotated_cookie.path
        == initial_cookie.path
        == settings
        .refresh_cookie_path
    )