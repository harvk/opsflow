from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy import (
    select,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.security import (
    create_access_token,
    verify_password,
)

from app.models.auth_session import (
    AuthSessionModel,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.user_service import (
    UserService,
)

from app.core.auth_response_messages import (
    PASSWORD_CHANGE_REJECTED_MESSAGE,
)


OLD_PASSWORD = (
    "VerySecurePassword123!"
)

NEW_PASSWORD = (
    "AnEvenLongerReplacementPassword456!"
)

SECOND_NEW_PASSWORD = (
    "AnotherSecureReplacementPassword789!"
)


# =========================================================
# HELPERS
# =========================================================


def create_user(
    db_session: Session,
):
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

    user = service.create_user(
        email=(
            f"password-change-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Password Change Test User"
        ),
        password=(
            OLD_PASSWORD
        ),
    )

    db_session.flush()

    return user


def issue_reauthentication(
    client: TestClient,
    *,
    access_token: str,
    password: str,
) -> str:
    response = client.post(
        "/api/v1/auth/reauthenticate",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "password": password,
        },
    )

    assert (
        response.status_code
        == 200
    )

    return (
        response.json()[
            "reauth_token"
        ]
    )


# =========================================================
# AUTHORIZATION REQUIREMENTS
# =========================================================


def test_change_password_requires_access_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/change-password",
        json={
            "reauth_token": (
                "not-a-real-token"
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )


def test_change_password_rejects_invalid_reauth_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                "not-a-valid-reauth-token"
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "Valid recent reauthentication "
            "is required."
        )
    }


# =========================================================
# PASSWORD POLICY
# =========================================================


def test_change_password_rejects_short_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                reauth_token
            ),
            "new_password": (
                "too-short"
            ),
        },
    )

    # Pydantic rejects the request before the service is
    # invoked.
    assert (
        response.status_code
        == 422
    )


def test_change_password_rejects_current_password_as_new_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                reauth_token
            ),
            "new_password": (
                OLD_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 400
    )

    assert response.json() == {
        "detail": (
            PASSWORD_CHANGE_REJECTED_MESSAGE
        )
    }


# =========================================================
# SUCCESSFUL CHANGE
# =========================================================


def test_change_password_replaces_stored_password_hash(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    before = (
        repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        before is not None
    )

    old_hash = (
        before.hashed_password
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                reauth_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    after = (
        repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        after is not None
    )

    assert (
        after.hashed_password
        != old_hash
    )

    assert verify_password(
        NEW_PASSWORD,
        after.hashed_password,
    )

    assert not verify_password(
        OLD_PASSWORD,
        after.hashed_password,
    )


def test_change_password_revokes_all_refresh_sessions(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    # Create two persistent login sessions.
    login_one = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                user.email
            ),
            "password": (
                OLD_PASSWORD
            ),
        },
    )

    assert (
        login_one.status_code
        == 200
    )

    login_two = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                user.email
            ),
            "password": (
                OLD_PASSWORD
            ),
        },
    )

    assert (
        login_two.status_code
        == 200
    )

    access_token = (
        login_two.json()[
            "access_token"
        ]
    )

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                reauth_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    sessions = (
        db_session.execute(
            select(
                AuthSessionModel
            )
            .where(
                AuthSessionModel.user_id
                == user.id
            )
        )
        .scalars()
        .all()
    )

    assert (
        len(sessions)
        >= 2
    )

    assert all(
        session.revoked_at
        is not None
        for session in sessions
    )

    assert all(
        session.revocation_reason
        == "password_changed"
        for session in sessions
    )


def test_change_password_clears_browser_auth_cookies(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                user.email
            ),
            "password": (
                OLD_PASSWORD
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    access_token = (
        login_response.json()[
            "access_token"
        ]
    )

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    response = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                reauth_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        response.status_code
        == 204
    )

    # TestClient's cookie jar processes the Set-Cookie
    # expirations sent by the endpoint.
    assert (
        client.cookies.get(
            "opsflow_refresh_token"
        )
        is None
    )

    assert (
        client.cookies.get(
            "opsflow_csrf"
        )
        is None
    )


# =========================================================
# OLD AND NEW PASSWORD BEHAVIOR
# =========================================================


def test_old_password_fails_and_new_password_succeeds_after_change(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    After a successful password change:

        old password must fail
        new password must succeed

    The pytest TestClient intentionally reuses the same
    SQLAlchemy Session for every request within this test.

    Production requests use fresh request-scoped sessions.

    expire_all() therefore prevents SQLAlchemy's test identity
    map from serving credential state loaded before the
    password update.
    """

    # =====================================================
    # CREATE USER
    # =====================================================

    user = create_user(
        db_session
    )

    # =====================================================
    # ISSUE ACCESS TOKEN
    # =====================================================

    access_token = (
        create_access_token(
            user.id
        )
    )

    # =====================================================
    # REAUTHENTICATE WITH CURRENT PASSWORD
    # =====================================================

    reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    # =====================================================
    # CHANGE PASSWORD
    # =====================================================

    change_response = (
        client.post(
            "/api/v1/auth/change-password",
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                )
            },
            json={
                "reauth_token": (
                    reauth_token
                ),
                "new_password": (
                    NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        change_response.status_code
        == 204
    )

    # =====================================================
    # IMPORTANT TEST-SESSION REFRESH
    # =====================================================

    # conftest.py intentionally gives every TestClient
    # request in this test the SAME SQLAlchemy Session.
    #
    # Password change uses a SQL UPDATE. Expire ORM state so
    # the next authentication query reloads the credential
    # from PostgreSQL rather than potentially reusing the
    # pre-change password hash from SQLAlchemy's identity
    # map.
    #
    # The UPDATE has already been flushed, so this SELECT can
    # see the replacement hash even though pytest's outer
    # transaction remains uncommitted.
    db_session.expire_all()

    # =====================================================
    # VERIFY DATABASE CREDENTIAL STATE DIRECTLY
    # =====================================================

    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    auth_record = (
        repository
        .get_auth_record_by_email(
            user.email
        )
    )

    assert (
        auth_record
        is not None
    )

    # New credential must now be stored.
    assert verify_password(
        NEW_PASSWORD,
        auth_record.hashed_password,
    )

    # Old credential must no longer match.
    assert not verify_password(
        OLD_PASSWORD,
        auth_record.hashed_password,
    )

    # Expire once more before exercising the actual HTTP
    # authentication boundary.
    db_session.expire_all()

    # =====================================================
    # OLD PASSWORD MUST FAIL
    # =====================================================

    old_login = (
        client.post(
            "/api/v1/auth/token",
            data={
                "username": (
                    user.email
                ),
                "password": (
                    OLD_PASSWORD
                ),
            },
        )
    )

    assert (
        old_login.status_code
        == 401
    )

    # =====================================================
    # NEW PASSWORD MUST SUCCEED
    # =====================================================

    # The failed old-password login above may have loaded the
    # user again into the test session. Expiring here keeps
    # this multi-request test representative of separate
    # production request sessions.
    db_session.expire_all()

    new_login = (
        client.post(
            "/api/v1/auth/token",
            data={
                "username": (
                    user.email
                ),
                "password": (
                    NEW_PASSWORD
                ),
            },
        )
    )

    assert (
        new_login.status_code
        == 200
    )

    assert (
        new_login.json()[
            "access_token"
        ]
    )


# =========================================================
# STALE REAUTH PROOF
# =========================================================


def test_old_reauth_token_becomes_stale_after_password_change(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    old_reauth_token = (
        issue_reauthentication(
            client,
            access_token=(
                access_token
            ),
            password=(
                OLD_PASSWORD
            ),
        )
    )

    first_change = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                old_reauth_token
            ),
            "new_password": (
                NEW_PASSWORD
            ),
        },
    )

    assert (
        first_change.status_code
        == 204
    )

    # The access JWT is stateless and may still be inside
    # its normal short lifetime.
    #
    # The OLD reauthentication proof must nevertheless fail,
    # because its credential fingerprint refers to the old
    # password hash.
    second_change = client.post(
        "/api/v1/auth/change-password",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "reauth_token": (
                old_reauth_token
            ),
            "new_password": (
                SECOND_NEW_PASSWORD
            ),
        },
    )

    assert (
        second_change.status_code
        == 403
    )