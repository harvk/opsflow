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

from app.services.user_service import (
    UserService,
)


def create_user(
    db_session: Session,
):
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = UserService(
        user_repository
    )

    user = user_service.create_user(
        email=(
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name="Session Test User",
        password=(
            "VerySecurePassword123!"
        ),
    )

    db_session.flush()

    return user


def create_auth_session(
    *,
    user_id,
) -> AuthSession:
    now = datetime.now(
        timezone.utc
    )

    return AuthSession(
        id=uuid4(),
        user_id=user_id,
        current_jti=uuid4(),
        created_at=now,
        last_used_at=now,
        expires_at=(
            now
            + timedelta(
                days=7
            )
        ),
    )


def test_create_and_get_auth_session(
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    auth_session = (
        create_auth_session(
            user_id=user.id
        )
    )

    repository.create(
        auth_session
    )

    result = repository.get_by_id(
        auth_session.id
    )

    assert result is not None

    assert (
        result.id
        == auth_session.id
    )

    assert (
        result.user_id
        == user.id
    )

    assert (
        result.current_jti
        == auth_session.current_jti
    )

    assert (
        result.revoked_at
        is None
    )


def test_update_current_token_rotates_jti(
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    auth_session = (
        create_auth_session(
            user_id=user.id
        )
    )

    repository.create(
        auth_session
    )

    replacement_jti = uuid4()

    replacement_time = (
        datetime.now(
            timezone.utc
        )
    )

    repository.update_current_token(
        session_id=(
            auth_session.id
        ),
        current_jti=(
            replacement_jti
        ),
        last_used_at=(
            replacement_time
        ),
    )

    result = repository.get_by_id(
        auth_session.id
    )

    assert result is not None

    assert (
        result.current_jti
        == replacement_jti
    )


def test_revoke_session(
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    auth_session = (
        create_auth_session(
            user_id=user.id
        )
    )

    repository.create(
        auth_session
    )

    revoked_at = datetime.now(
        timezone.utc
    )

    repository.revoke(
        session_id=(
            auth_session.id
        ),
        revoked_at=(
            revoked_at
        ),
        reason="logout",
    )

    result = repository.get_by_id(
        auth_session.id
    )

    assert result is not None
    assert result.is_revoked

    assert (
        result.revocation_reason
        == "logout"
    )


def test_revoke_all_for_user(
    db_session: Session,
) -> None:
    user = create_user(
        db_session
    )

    repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    first = create_auth_session(
        user_id=user.id
    )

    second = create_auth_session(
        user_id=user.id
    )

    repository.create(
        first
    )

    repository.create(
        second
    )

    count = (
        repository
        .revoke_all_for_user(
            user_id=user.id,
            revoked_at=(
                datetime.now(
                    timezone.utc
                )
            ),
            reason="logout_all",
        )
    )

    assert count == 2

    first_result = (
        repository.get_by_id(
            first.id
        )
    )

    second_result = (
        repository.get_by_id(
            second.id
        )
    )

    assert first_result is not None
    assert second_result is not None

    assert first_result.is_revoked
    assert second_result.is_revoked