from __future__ import annotations

from uuid import (
    uuid4,
)

import pytest

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    decode_refresh_token,
)

from app.domain.user import (
    UserRole,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.authentication_service import (
    AuthenticationService,
    InvalidCredentialsError,
    InvalidCsrfTokenError,
)

from app.services.user_service import (
    UserService,
)


# =========================================================
# TEST CONSTANTS
# =========================================================


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# TEST HELPERS
# =========================================================


def build_authentication_service(
    db_session: Session,
) -> tuple[
    AuthenticationService,
    SqlAlchemyUserRepository,
    SqlAlchemyAuthSessionRepository,
]:
    """
    Construct the authentication service with both of its
    persistence dependencies using the current test database
    transaction.
    """

    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    authentication_service = (
        AuthenticationService(
            repository=(
                user_repository
            ),
            auth_session_repository=(
                session_repository
            ),
        )
    )

    return (
        authentication_service,
        user_repository,
        session_repository,
    )


def create_test_user(
    user_repository: (
        SqlAlchemyUserRepository
    ),
):
    """
    Create a unique user for a session-revocation test.
    """

    user_service = (
        UserService(
            user_repository
        )
    )

    user = user_service.create_user(
        email=(
            f"session-revocation-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Session Revocation Test User"
        ),
        password=(
            TEST_PASSWORD
        ),
        role=(
            UserRole.ADMIN
        ),
    )

    return user


# =========================================================
# CURRENT-SESSION REVOCATION
# =========================================================


def test_logout_revokes_current_session(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
        session_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    login_result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    revocation_result = (
        authentication_service
        .revoke_refresh_session_with_csrf(
            login_result.refresh_token,
            csrf_cookie=(
                login_result.csrf_token
            ),
            csrf_header=(
                login_result.csrf_token
            ),
        )
    )

    assert (
        revocation_result.user.id
        == user.id
    )

    assert (
        revocation_result.session_id
        == login_result.session_id
    )

    persisted_session = (
        session_repository
        .get_by_id(
            login_result.session_id
        )
    )

    assert (
        persisted_session
        is not None
    )

    assert (
        persisted_session.revoked_at
        is not None
    )

    assert (
        persisted_session.revocation_reason
        == "logout"
    )


# =========================================================
# LOGGED-OUT SESSION CANNOT REFRESH
# =========================================================


def test_logged_out_session_cannot_refresh(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
        _,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    login_result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    authentication_service.revoke_refresh_session_with_csrf(
        login_result.refresh_token,
        csrf_cookie=(
            login_result.csrf_token
        ),
        csrf_header=(
            login_result.csrf_token
        ),
    )

    with pytest.raises(
        InvalidCredentialsError
    ):
        (
            authentication_service
            .rotate_refresh_token_with_csrf(
                login_result.refresh_token,
                csrf_cookie=(
                    login_result.csrf_token
                ),
                csrf_header=(
                    login_result.csrf_token
                ),
            )
        )


# =========================================================
# INVALID CSRF MUST NOT REVOKE SESSION
# =========================================================


def test_invalid_csrf_does_not_revoke_session(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
        session_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    login_result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    with pytest.raises(
        InvalidCsrfTokenError
    ):
        (
            authentication_service
            .revoke_refresh_session_with_csrf(
                login_result.refresh_token,
                csrf_cookie=(
                    login_result.csrf_token
                ),
                csrf_header=(
                    "incorrect-csrf-value"
                ),
            )
        )

    persisted_session = (
        session_repository
        .get_by_id(
            login_result.session_id
        )
    )

    assert (
        persisted_session
        is not None
    )

    assert (
        persisted_session.revoked_at
        is None
    )

    assert (
        persisted_session.revocation_reason
        is None
    )


# =========================================================
# LOGOUT ALL
# =========================================================


def test_logout_all_revokes_multiple_user_sessions(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
        session_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    first_session = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    second_session = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    revoked_count = (
        authentication_service
        .revoke_all_sessions_for_user(
            user
        )
    )

    assert (
        revoked_count
        == 2
    )

    first_persisted = (
        session_repository
        .get_by_id(
            first_session.session_id
        )
    )

    second_persisted = (
        session_repository
        .get_by_id(
            second_session.session_id
        )
    )

    assert (
        first_persisted
        is not None
    )

    assert (
        second_persisted
        is not None
    )

    assert (
        first_persisted.revoked_at
        is not None
    )

    assert (
        second_persisted.revoked_at
        is not None
    )

    assert (
        first_persisted.revocation_reason
        == "logout_all"
    )

    assert (
        second_persisted.revocation_reason
        == "logout_all"
    )


# =========================================================
# LOGOUT ALL MUST NOT AFFECT OTHER USERS
# =========================================================


def test_logout_all_does_not_revoke_other_user_sessions(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
        session_repository,
    ) = build_authentication_service(
        db_session
    )

    first_user = (
        create_test_user(
            user_repository
        )
    )

    second_user = (
        create_test_user(
            user_repository
        )
    )

    first_session = (
        authentication_service
        .issue_authentication_result(
            first_user
        )
    )

    second_session = (
        authentication_service
        .issue_authentication_result(
            second_user
        )
    )

    authentication_service.revoke_all_sessions_for_user(
        first_user
    )

    first_persisted = (
        session_repository
        .get_by_id(
            first_session.session_id
        )
    )

    second_persisted = (
        session_repository
        .get_by_id(
            second_session.session_id
        )
    )

    assert (
        first_persisted
        is not None
    )

    assert (
        second_persisted
        is not None
    )

    assert (
        first_persisted.revoked_at
        is not None
    )

    assert (
        first_persisted.revocation_reason
        == "logout_all"
    )

    assert (
        second_persisted.revoked_at
        is None
    )

    assert (
        second_persisted.revocation_reason
        is None
    )


# =========================================================
# HTTP LOGOUT
# =========================================================


def test_logout_revokes_server_side_session(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Verify that POST /auth/logout does more than delete
    browser cookies.

    It must also persist revocation in auth_sessions.
    """

    # -----------------------------------------------------
    # CREATE TEST USER
    # -----------------------------------------------------

    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = create_test_user(
        user_repository
    )

    # -----------------------------------------------------
    # LOGIN
    # -----------------------------------------------------

    login_response = (
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
        login_response.status_code
        == 200
    )

    # -----------------------------------------------------
    # CAPTURE BROWSER SESSION STATE
    # -----------------------------------------------------

    refresh_token = (
        client.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    csrf_token = (
        client.cookies.get(
            settings
            .csrf_cookie_name
        )
    )

    assert (
        refresh_token
        is not None
    )

    assert (
        csrf_token
        is not None
    )

    claims = (
        decode_refresh_token(
            refresh_token
        )
    )

    # -----------------------------------------------------
    # LOGOUT
    # -----------------------------------------------------

    logout_response = (
        client.post(
            "/api/v1/auth/logout",
            headers={
                settings
                .csrf_header_name: (
                    csrf_token
                )
            },
        )
    )

    assert (
        logout_response.status_code
        == 204
    )

    # -----------------------------------------------------
    # VERIFY SERVER-SIDE REVOCATION
    # -----------------------------------------------------

    session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    persisted_session = (
        session_repository
        .get_by_id(
            claims.session_id
        )
    )

    assert (
        persisted_session
        is not None
    )

    assert (
        persisted_session.revoked_at
        is not None
    )

    assert (
        persisted_session.revocation_reason
        == "logout"
    )


# =========================================================
# HTTP LOGOUT ALL
# =========================================================


def test_logout_all_revokes_all_server_side_sessions(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Verify that POST /auth/logout-all revokes every
    persistent refresh session owned by the bearer-
    authenticated user.
    """

    # -----------------------------------------------------
    # CREATE USER
    # -----------------------------------------------------

    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = create_test_user(
        user_repository
    )

    # -----------------------------------------------------
    # FIRST LOGIN
    # -----------------------------------------------------

    first_login = (
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
        first_login.status_code
        == 200
    )

    first_refresh_token = (
        client.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    assert (
        first_refresh_token
        is not None
    )

    first_claims = (
        decode_refresh_token(
            first_refresh_token
        )
    )

    # -----------------------------------------------------
    # SECOND LOGIN
    # -----------------------------------------------------

    second_login = (
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
        second_login.status_code
        == 200
    )

    second_refresh_token = (
        client.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    assert (
        second_refresh_token
        is not None
    )

    second_claims = (
        decode_refresh_token(
            second_refresh_token
        )
    )

    assert (
        first_claims.session_id
        != second_claims.session_id
    )

    # The second login response contains the current access
    # token that authorizes /logout-all.
    access_token = (
        second_login.json()[
            "access_token"
        ]
    )

    # -----------------------------------------------------
    # LOGOUT EVERYWHERE
    # -----------------------------------------------------

    logout_all_response = (
        client.post(
            "/api/v1/auth/logout-all",
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                )
            },
        )
    )

    assert (
        logout_all_response.status_code
        == 204
    )

    # -----------------------------------------------------
    # VERIFY BOTH SESSIONS
    # -----------------------------------------------------

    session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    first_persisted = (
        session_repository
        .get_by_id(
            first_claims.session_id
        )
    )

    second_persisted = (
        session_repository
        .get_by_id(
            second_claims.session_id
        )
    )

    assert (
        first_persisted
        is not None
    )

    assert (
        second_persisted
        is not None
    )

    assert (
        first_persisted.revoked_at
        is not None
    )

    assert (
        second_persisted.revoked_at
        is not None
    )

    assert (
        first_persisted.revocation_reason
        == "logout_all"
    )

    assert (
        second_persisted.revocation_reason
        == "logout_all"
    )