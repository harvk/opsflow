from uuid import uuid4

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

from app.services.user_service import (
    UserService,
)


def create_api_test_user(
    db_session: Session,
):
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = UserService(
        repository
    )

    user = service.create_user(
        email=(
            f"refresh-api-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Refresh API Test User"
        ),
        password=(
            "VerySecurePassword123!"
        ),
        role=(
            UserRole.ADMIN
        ),
    )

    db_session.flush()

    return user


def test_refresh_endpoint_rotates_refresh_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_api_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                user.email
            ),
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    original_refresh_token = (
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
        original_refresh_token
        is not None
    )

    assert csrf_token is not None

    original_claims = (
        decode_refresh_token(
            original_refresh_token
        )
    )

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        headers={
            settings
            .csrf_header_name: (
                csrf_token
            )
        },
    )

    assert (
        refresh_response.status_code
        == 200
    )

    replacement_refresh_token = (
        client.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    assert (
        replacement_refresh_token
        is not None
    )

    assert (
        replacement_refresh_token
        != original_refresh_token
    )

    replacement_claims = (
        decode_refresh_token(
            replacement_refresh_token
        )
    )

    assert (
        replacement_claims.session_id
        == original_claims.session_id
    )

    assert (
        replacement_claims.token_id
        != original_claims.token_id
    )


def test_replaying_consumed_refresh_token_revokes_session(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_api_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                user.email
            ),
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    original_refresh_token = (
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
        original_refresh_token
        is not None
    )

    assert csrf_token is not None

    original_claims = (
        decode_refresh_token(
            original_refresh_token
        )
    )

    # -----------------------------------------------------
    # FIRST USE — VALID
    # -----------------------------------------------------

    first_refresh = client.post(
        "/api/v1/auth/refresh",
        headers={
            settings
            .csrf_header_name: (
                csrf_token
            )
        },
    )

    assert (
        first_refresh.status_code
        == 200
    )

    replacement_refresh_token = (
        client.cookies.get(
            settings
            .refresh_cookie_name
        )
    )

    assert (
        replacement_refresh_token
        is not None
    )

    assert (
        replacement_refresh_token
        != original_refresh_token
    )

    # -----------------------------------------------------
    # REPLAY OLD TOKEN
    # -----------------------------------------------------

    # Force the browser cookie jar back to the already-used
    # refresh credential while retaining the session-bound
    # CSRF token.
    client.cookies.set(
        settings.refresh_cookie_name,
        original_refresh_token,
        path=(
            settings
            .refresh_cookie_path
        ),
    )

    replay_response = client.post(
        "/api/v1/auth/refresh",
        headers={
            settings
            .csrf_header_name: (
                csrf_token
            )
        },
    )

    assert (
        replay_response.status_code
        == 401
    )

    assert replay_response.json() == {
        "detail": (
            "Could not refresh credentials."
        )
    }

    # -----------------------------------------------------
    # DATABASE REVOCATION SURVIVED THE 401 RESPONSE
    # -----------------------------------------------------

    session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    persisted_session = (
        session_repository
        .get_by_id(
            original_claims.session_id
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
        == "refresh_token_reuse"
    )