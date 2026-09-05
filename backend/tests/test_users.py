import pytest
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import (
    UserAlreadyExistsError,
    UserService,
)


def test_create_user_persists_user(
    db_session: Session,
) -> None:
    repository = SqlAlchemyUserRepository(
        db_session
    )

    service = UserService(repository)

    user = service.create_user(
        email="Admin@Example.com",
        full_name="OpsFlow Admin",
        password="VerySecurePassword123!",
        role=UserRole.ADMIN,
    )

    assert user.id is not None
    assert user.email == "admin@example.com"
    assert user.full_name == "OpsFlow Admin"
    assert user.role == UserRole.ADMIN
    assert user.is_active is True


def test_create_user_hashes_password(
    db_session: Session,
) -> None:
    repository = SqlAlchemyUserRepository(
        db_session
    )

    service = UserService(repository)

    password = "VerySecurePassword123!"

    service.create_user(
        email="operator@example.com",
        full_name="OpsFlow Operator",
        password=password,
        role=UserRole.OPERATOR,
    )

    auth_record = repository.get_auth_record_by_email(
        "operator@example.com"
    )

    assert auth_record is not None

    assert auth_record.hashed_password != password

    assert verify_password(
        password,
        auth_record.hashed_password,
    )


def test_duplicate_email_is_rejected(
    db_session: Session,
) -> None:
    repository = SqlAlchemyUserRepository(
        db_session
    )

    service = UserService(repository)

    service.create_user(
        email="user@example.com",
        full_name="First User",
        password="VerySecurePassword123!",
    )

    with pytest.raises(UserAlreadyExistsError):
        service.create_user(
            email="USER@example.com",
            full_name="Duplicate User",
            password="AnotherSecurePassword123!",
        )