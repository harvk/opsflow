from __future__ import annotations

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
    RefreshTokenReuseError,
)

from app.services.user_service import (
    UserService,
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
            f"refresh-rotation-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Refresh Rotation Test User"
        ),
        password=(
            "VerySecurePassword123!"
        ),
        role=(
            UserRole.ADMIN
        ),
    )


# =========================================================
# SUCCESSFUL ROTATION
# =========================================================


def test_refresh_rotation_replaces_current_jti(
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

    original_claims = (
        decode_refresh_token(
            login_result.refresh_token
        )
    )

    original_session = (
        session_repository
        .get_by_id(
            original_claims.session_id
        )
    )

    assert (
        original_session
        is not None
    )

    assert (
        original_session.current_jti
        == original_claims.token_id
    )

    rotation_result = (
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

    replacement_claims = (
        decode_refresh_token(
            rotation_result.refresh_token
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

    # Stable token family.
    assert (
        replacement_claims.session_id
        == original_claims.session_id
    )

    # Same authenticated user.
    assert (
        replacement_claims.user_id
        == original_claims.user_id
    )

    # One-time refresh-token identity changed.
    assert (
        replacement_claims.token_id
        != original_claims.token_id
    )

    # Database now accepts only the replacement jti.
    assert (
        persisted_session.current_jti
        == replacement_claims.token_id
    )

    # Rotation result and JWT agree.
    assert (
        rotation_result.refresh_token_id
        == replacement_claims.token_id
    )

    assert (
        rotation_result.previous_refresh_token_id
        == original_claims.token_id
    )


def test_refresh_rotation_preserves_absolute_expiration(
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

    original_claims = (
        decode_refresh_token(
            login_result.refresh_token
        )
    )

    rotation_result = (
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

    replacement_claims = (
        decode_refresh_token(
            rotation_result.refresh_token
        )
    )

    assert abs(
        (
            replacement_claims.expires_at
            - original_claims.expires_at
        ).total_seconds()
    ) < 1


def test_refresh_rotation_preserves_csrf_session_binding(
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

    rotation_result = (
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

    replacement_claims = (
        decode_refresh_token(
            rotation_result.refresh_token
        )
    )

    assert validate_csrf_token(
        replacement_claims.session_id,
        login_result.csrf_token,
    )


# =========================================================
# REUSE DETECTION
# =========================================================


def test_consumed_refresh_token_reuse_revokes_session(
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

    original_claims = (
        decode_refresh_token(
            login_result.refresh_token
        )
    )

    # First use is legitimate.
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

    # Second use of the SAME original credential is replay.
    with pytest.raises(
        RefreshTokenReuseError
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


def test_replacement_token_is_rejected_after_reuse_detection(
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

    rotation_result = (
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

    # Replay the now-consumed original token.
    with pytest.raises(
        RefreshTokenReuseError
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

    # Because reuse revokes the entire token family, even the
    # otherwise-current replacement credential is unusable.
    with pytest.raises(
        InvalidCredentialsError
    ):
        (
            authentication_service
            .rotate_refresh_token_with_csrf(
                rotation_result.refresh_token,
                csrf_cookie=(
                    login_result.csrf_token
                ),
                csrf_header=(
                    login_result.csrf_token
                ),
            )
        )


# =========================================================
# INVALID CSRF MUST NOT ROTATE
# =========================================================


def test_invalid_csrf_does_not_rotate_current_jti(
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

    original_claims = (
        decode_refresh_token(
            login_result.refresh_token
        )
    )

    with pytest.raises(
        InvalidCsrfTokenError
    ):
        (
            authentication_service
            .rotate_refresh_token_with_csrf(
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
            original_claims.session_id
        )
    )

    assert (
        persisted_session
        is not None
    )

    assert (
        persisted_session.current_jti
        == original_claims.token_id
    )

    assert (
        persisted_session.revoked_at
        is None
    )