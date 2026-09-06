import pytest
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.authentication_service import (
    InactiveUserError,
    InvalidCredentialsError,
    AuthenticationService,
)
from app.services.user_service import (
    UserService,
)


def test_authenticate_valid_credentials(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = UserService(
        repository
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    user_service.create_user(
        email="operator@example.com",
        full_name="Test Operator",
        password="VerySecurePassword123!",
        role=UserRole.OPERATOR,
    )

    authenticated_user = (
        authentication_service.authenticate(
            email="operator@example.com",
            password="VerySecurePassword123!",
        )
    )

    assert (
        authenticated_user.email
        == "operator@example.com"
    )

    assert (
        authenticated_user.role
        == UserRole.OPERATOR
    )


def test_authenticate_normalizes_email(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = UserService(
        repository
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    user_service.create_user(
        email="user@example.com",
        full_name="Test User",
        password="VerySecurePassword123!",
    )

    user = authentication_service.authenticate(
        email="  USER@EXAMPLE.COM  ",
        password="VerySecurePassword123!",
    )

    assert user.email == "user@example.com"


def test_wrong_password_is_rejected(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = UserService(
        repository
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    user_service.create_user(
        email="user@example.com",
        full_name="Test User",
        password="VerySecurePassword123!",
    )

    with pytest.raises(
        InvalidCredentialsError
    ):
        authentication_service.authenticate(
            email="user@example.com",
            password="WrongPassword123!",
        )


def test_unknown_email_is_rejected(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    with pytest.raises(
        InvalidCredentialsError
    ):
        authentication_service.authenticate(
            email="missing@example.com",
            password="WrongPassword123!",
        )


def test_inactive_user_cannot_authenticate(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    repository.add(
        email="inactive@example.com",
        full_name="Inactive User",
        hashed_password=hash_password(
            "VerySecurePassword123!"
        ),
        role=UserRole.VIEWER,
        is_active=False,
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    with pytest.raises(
        InactiveUserError
    ):
        authentication_service.authenticate(
            email="inactive@example.com",
            password="VerySecurePassword123!",
        )


def test_access_token_resolves_current_user(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user_service = UserService(
        repository
    )

    authentication_service = (
        AuthenticationService(
            repository
        )
    )

    user = user_service.create_user(
        email="operator@example.com",
        full_name="Test Operator",
        password="VerySecurePassword123!",
        role=UserRole.OPERATOR,
    )

    token = (
        authentication_service.issue_access_token(
            user
        )
    )

    resolved_user = (
        authentication_service.resolve_access_token(
            token
        )
    )

    assert resolved_user.id == user.id
    assert resolved_user.email == user.email