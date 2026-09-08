from datetime import (
    datetime,
    timezone,
)
from uuid import uuid4

import pytest
from sqlalchemy.orm import (
    Session,
)

from app.core.security import (
    decode_refresh_token,
    validate_csrf_token,
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


def build_authentication_service(
    db_session: Session,
) -> tuple[
    AuthenticationService,
    SqlAlchemyUserRepository,
    SqlAlchemyAuthSessionRepository,
]:
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
    user_service = (
        UserService(
            user_repository
        )
    )

    return user_service.create_user(
        email=(
            f"session-test-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Authentication Session Test"
        ),
        password=(
            "VerySecurePassword123!"
        ),
        role=(
            UserRole.ADMIN
        ),
    )


def test_login_result_creates_persistent_session(
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

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    claims = (
        decode_refresh_token(
            result.refresh_token
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
        persisted_session.id
        == claims.session_id
    )

    assert (
        persisted_session.user_id
        == user.id
    )

    assert (
        persisted_session.current_jti
        == claims.token_id
    )

    assert (
        result.session_id
        == persisted_session.id
    )

    assert (
        result.refresh_token_id
        == persisted_session.current_jti
    )

    assert validate_csrf_token(
        persisted_session.id,
        result.csrf_token,
    )


def test_refresh_resolves_valid_persistent_session(
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

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    context = (
        authentication_service
        .resolve_refresh_token_with_csrf(
            result.refresh_token,
            csrf_cookie=(
                result.csrf_token
            ),
            csrf_header=(
                result.csrf_token
            ),
        )
    )

    assert (
        context.user.id
        == user.id
    )

    assert (
        context.session.id
        == result.session_id
    )

    assert (
        context.claims.token_id
        == result.refresh_token_id
    )


def test_refresh_rejects_mismatched_csrf_header(
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

    result = (
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
            .resolve_refresh_token_with_csrf(
                result.refresh_token,
                csrf_cookie=(
                    result.csrf_token
                ),
                csrf_header=(
                    "not-the-cookie-value"
                ),
            )
        )


def test_csrf_from_second_session_cannot_refresh_first_session(
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

    first_result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    second_result = (
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
            .resolve_refresh_token_with_csrf(
                first_result.refresh_token,
                csrf_cookie=(
                    second_result.csrf_token
                ),
                csrf_header=(
                    second_result.csrf_token
                ),
            )
        )


def test_refresh_rejects_token_that_is_not_current(
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

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    session_repository.update_current_token(
        session_id=(
            result.session_id
        ),
        current_jti=(
            uuid4()
        ),
        last_used_at=(
            datetime.now(
                timezone.utc
            )
        ),
    )

    with pytest.raises(
        InvalidCredentialsError
    ):
        (
            authentication_service
            .resolve_refresh_token_with_csrf(
                result.refresh_token,
                csrf_cookie=(
                    result.csrf_token
                ),
                csrf_header=(
                    result.csrf_token
                ),
            )
        )


def test_refresh_rejects_revoked_session(
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

    result = (
        authentication_service
        .issue_authentication_result(
            user
        )
    )

    session_repository.revoke(
        session_id=(
            result.session_id
        ),
        revoked_at=(
            datetime.now(
                timezone.utc
            )
        ),
        reason=(
            "test-revocation"
        ),
    )

    with pytest.raises(
        InvalidCredentialsError
    ):
        (
            authentication_service
            .resolve_refresh_token_with_csrf(
                result.refresh_token,
                csrf_cookie=(
                    result.csrf_token
                ),
                csrf_header=(
                    result.csrf_token
                ),
            )
        )