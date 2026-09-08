from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
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
# TEST CREDENTIALS
# =========================================================


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# USER FACTORY
# =========================================================


def create_refresh_lifetime_user(
    db_session: Session,
) -> User:
    """
    Create one isolated active user.

    A unique account prevents these tests from sharing
    account-level login-throttle state with another test.
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
                "refresh-lifetime-"
                f"{uuid4().hex}"
                "@example.com"
            ),
            full_name=(
                "Refresh Lifetime User"
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
# COOKIE HELPERS
# =========================================================


def require_cookie(
    client: TestClient,
    cookie_name: str,
) -> str:
    """
    Read one browser cookie that must exist.
    """

    value = (
        client.cookies.get(
            cookie_name
        )
    )

    assert (
        value
        is not None
    ), (
        f"Expected cookie "
        f"{cookie_name!r} "
        "to be present."
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
) -> tuple[
    str,
    str,
]:
    """
    Establish a real application authentication session.

    Returns:

        refresh token
        CSRF token
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

        refresh_token = (
            require_cookie(
                client,
                settings
                .refresh_cookie_name,
            )
        )

        csrf_token = (
            require_cookie(
                client,
                settings
                .csrf_cookie_name,
            )
        )

        return (
            refresh_token,
            csrf_token,
        )

    finally:
        get_login_throttle.cache_clear()


# =========================================================
# REFRESH HELPER
# =========================================================


def rotate_refresh_token(
    client: TestClient,
    *,
    csrf_token: str,
) -> str:
    """
    Perform one real HTTP refresh rotation and return the
    replacement refresh JWT stored in the cookie jar.
    """

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

    assert (
        response.status_code
        == 200
    ), response.text

    body = (
        response.json()
    )

    assert (
        isinstance(
            body.get(
                "access_token"
            ),
            str,
        )
    )

    assert (
        body[
            "access_token"
        ]
    )

    return (
        require_cookie(
            client,
            settings
            .refresh_cookie_name,
        )
    )


# =========================================================
# DATABASE SESSION READER
# =========================================================


def read_persistent_session(
    db_session: Session,
    *,
    session_id,
):
    """
    Read the persistent auth-session state using the same
    transactional test database used by the HTTP client.
    """

    return (
        db_session.execute(
            text(
                """
                SELECT
                    id,
                    user_id,
                    current_jti,
                    created_at,
                    last_used_at,
                    expires_at,
                    revoked_at,
                    revocation_reason
                FROM auth_sessions
                WHERE id = :session_id
                """
            ),
            {
                "session_id": (
                    session_id
                ),
            },
        )
        .mappings()
        .one()
    )


# =========================================================
# INITIAL EXPIRATION CONTRACT
# =========================================================


def test_initial_refresh_token_expiration_matches_persistent_session(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Initial login must create one shared absolute expiration
    boundary for both:

        persistent auth-session row
        refresh JWT

    The JWT expiration may have second precision while the
    database datetime retains microseconds, so timestamps are
    compared at whole-second precision.
    """

    user = (
        create_refresh_lifetime_user(
            db_session
        )
    )

    (
        refresh_token,
        _,
    ) = (
        login(
            client,
            user=user,
        )
    )

    claims = (
        decode_refresh_token(
            refresh_token
        )
    )

    session_row = (
        read_persistent_session(
            db_session,
            session_id=(
                claims.session_id
            ),
        )
    )

    assert (
        session_row[
            "user_id"
        ]
        == user.id
    )

    assert (
        session_row[
            "current_jti"
        ]
        == claims.token_id
    )

    database_expiration = (
        session_row[
            "expires_at"
        ]
    )

    assert isinstance(
        database_expiration,
        datetime,
    )

    assert (
        int(
            database_expiration
            .timestamp()
        )
        == int(
            claims
            .expires_at
            .timestamp()
        )
    )

    # The session should represent approximately the
    # configured absolute lifetime from creation.

    configured_lifetime = (
        timedelta(
            days=(
                settings
                .refresh_token_expire_days
            )
        )
    )

    actual_lifetime = (
        database_expiration
        - session_row[
            "created_at"
        ]
    )

    assert (
        abs(
            (
                actual_lifetime
                - configured_lifetime
            )
            .total_seconds()
        )
        < 1
    )


# =========================================================
# NON-SLIDING ROTATION CONTRACT
# =========================================================


def test_repeated_refresh_rotation_preserves_absolute_expiration(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Repeated refresh-token rotation must change only the
    one-time token identity.

    It must NOT:

        create a new persistent session
        extend session.expires_at
        extend JWT exp
    """

    user = (
        create_refresh_lifetime_user(
            db_session
        )
    )

    (
        initial_refresh_token,
        csrf_token,
    ) = (
        login(
            client,
            user=user,
        )
    )

    initial_claims = (
        decode_refresh_token(
            initial_refresh_token
        )
    )

    initial_row = (
        read_persistent_session(
            db_session,
            session_id=(
                initial_claims
                .session_id
            ),
        )
    )

    initial_expiration = (
        initial_row[
            "expires_at"
        ]
    )

    initial_expiration_seconds = (
        int(
            initial_expiration
            .timestamp()
        )
    )

    initial_token_expiration_seconds = (
        int(
            initial_claims
            .expires_at
            .timestamp()
        )
    )

    assert (
        initial_expiration_seconds
        == initial_token_expiration_seconds
    )

    previous_token_id = (
        initial_claims
        .token_id
    )

    # -----------------------------------------------------
    # PERFORM MULTIPLE ROTATIONS
    # -----------------------------------------------------

    for _ in range(
        3
    ):
        replacement_token = (
            rotate_refresh_token(
                client,
                csrf_token=(
                    csrf_token
                ),
            )
        )

        replacement_claims = (
            decode_refresh_token(
                replacement_token
            )
        )

        # -------------------------------------------------
        # SAME SESSION FAMILY
        # -------------------------------------------------

        assert (
            replacement_claims
            .session_id
            == initial_claims
            .session_id
        )

        # -------------------------------------------------
        # NEW ONE-TIME TOKEN ID
        # -------------------------------------------------

        assert (
            replacement_claims
            .token_id
            != previous_token_id
        )

        # -------------------------------------------------
        # SAME ABSOLUTE JWT EXPIRATION
        # -------------------------------------------------

        assert (
            int(
                replacement_claims
                .expires_at
                .timestamp()
            )
            == (
                initial_token_expiration_seconds
            )
        )

        session_row = (
            read_persistent_session(
                db_session,
                session_id=(
                    initial_claims
                    .session_id
                ),
            )
        )

        # -------------------------------------------------
        # SAME DATABASE EXPIRATION
        # -------------------------------------------------

        assert (
            int(
                session_row[
                    "expires_at"
                ]
                .timestamp()
            )
            == (
                initial_expiration_seconds
            )
        )

        # -------------------------------------------------
        # DATABASE TRACKS CURRENT JTI
        # -------------------------------------------------

        assert (
            session_row[
                "current_jti"
            ]
            == (
                replacement_claims
                .token_id
            )
        )

        previous_token_id = (
            replacement_claims
            .token_id
        )


# =========================================================
# SERVER-SIDE ABSOLUTE EXPIRATION
# =========================================================


def test_expired_persistent_session_blocks_refresh_even_when_jwt_is_still_signed(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Persistent session state is an independent authorization
    boundary.

    Even if the refresh JWT is:

        correctly signed
        structurally valid
        not yet past its own exp

    an already-expired auth_sessions.expires_at must prevent
    rotation.
    """

    user = (
        create_refresh_lifetime_user(
            db_session
        )
    )

    (
        refresh_token,
        csrf_token,
    ) = (
        login(
            client,
            user=user,
        )
    )

    claims = (
        decode_refresh_token(
            refresh_token
        )
    )

    # The JWT is currently valid and should naturally expire
    # in the future.

    assert (
        claims.expires_at
        > datetime.now(
            timezone.utc
        )
    )

    forced_expiration = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=1
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
                forced_expiration
            ),
            "session_id": (
                claims.session_id
            ),
        },
    )

    db_session.flush()

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

    assert (
        response.status_code
        == 401
    ), response.text

    assert (
        response.json()
        == {
            "detail": (
                "Could not refresh credentials."
            ),
        }
    )

    # No rotation may have occurred.

    row = (
        read_persistent_session(
            db_session,
            session_id=(
                claims.session_id
            ),
        )
    )

    assert (
        row[
            "current_jti"
        ]
        == claims.token_id
    )