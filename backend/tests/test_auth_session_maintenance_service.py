from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

from uuid import (
    uuid4,
)

from sqlalchemy.orm import (
    Session,
)

from app.domain.auth_session import (
    AuthSession,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.auth_session_maintenance_service import (
    AuthSessionMaintenanceService,
)

from app.services.user_service import (
    UserService,
)


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


def create_test_user(
    db_session: Session,
):
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = (
        UserService(
            user_repository
        )
    )

    user = user_service.create_user(
        email=(
            f"session-cleanup-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Session Cleanup Test User"
        ),
        password=(
            TEST_PASSWORD
        ),
    )

    db_session.flush()

    return user


def create_session(
    *,
    user_id,
    created_at: datetime,
    expires_at: datetime,
) -> AuthSession:
    return AuthSession(
        id=(
            uuid4()
        ),
        user_id=user_id,
        current_jti=(
            uuid4()
        ),
        created_at=(
            created_at
        ),
        last_used_at=(
            created_at
        ),
        expires_at=(
            expires_at
        ),
        revoked_at=None,
        revocation_reason=None,
    )


def test_cleanup_deletes_only_sessions_past_retention(
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    now = datetime(
        2026,
        9,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    # Expired 45 days ago:
    # outside a 30-day retention window.
    old_expired = (
        create_session(
            user_id=(
                user.id
            ),
            created_at=(
                now
                - timedelta(
                    days=60
                )
            ),
            expires_at=(
                now
                - timedelta(
                    days=45
                )
            ),
        )
    )

    # Expired only 10 days ago:
    # retain for investigation.
    recently_expired = (
        create_session(
            user_id=(
                user.id
            ),
            created_at=(
                now
                - timedelta(
                    days=20
                )
            ),
            expires_at=(
                now
                - timedelta(
                    days=10
                )
            ),
        )
    )

    # Still active.
    active_session = (
        create_session(
            user_id=(
                user.id
            ),
            created_at=(
                now
                - timedelta(
                    days=2
                )
            ),
            expires_at=(
                now
                + timedelta(
                    days=5
                )
            ),
        )
    )

    repository.create(
        old_expired
    )

    repository.create(
        recently_expired
    )

    repository.create(
        active_session
    )

    maintenance_service = (
        AuthSessionMaintenanceService(
            repository,
            retention_days=30,
        )
    )

    deleted_count = (
        maintenance_service
        .purge_expired_sessions(
            now=now
        )
    )

    assert (
        deleted_count
        == 1
    )

    assert (
        repository.get_by_id(
            old_expired.id
        )
        is None
    )

    assert (
        repository.get_by_id(
            recently_expired.id
        )
        is not None
    )

    assert (
        repository.get_by_id(
            active_session.id
        )
        is not None
    )


def test_cleanup_requires_timezone_aware_time(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    maintenance_service = (
        AuthSessionMaintenanceService(
            repository,
            retention_days=30,
        )
    )

    naive_time = datetime(
        2026,
        9,
        7,
        12,
        0,
    )

    try:
        maintenance_service.purge_expired_sessions(
            now=naive_time
        )

    except ValueError:
        pass

    else:
        raise AssertionError(
            "Naive datetime should have "
            "been rejected."
        )