from __future__ import annotations

from datetime import UTC, datetime
from getpass import getpass

from sqlalchemy import select

from app.core.password_policy import (
    PasswordPolicyViolation,
    validate_new_password,
)
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.domain.user import UserRole
from app.models.user import UserModel
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import UserService

DEFAULT_ADMIN_EMAIL = "admin@example.com"


def main() -> None:
    """Create or repair a local administrator without hard-coded credentials."""

    print("Recover OpsFlow Administrator")
    print("-----------------------------")

    email_input = input(
        f"Administrator email [{DEFAULT_ADMIN_EMAIL}]: "
    ).strip()

    email = (
        email_input
        or DEFAULT_ADMIN_EMAIL
    ).lower()

    password = getpass("New password: ")
    confirm_password = getpass("Confirm new password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    try:
        validate_new_password(password)
    except PasswordPolicyViolation as exc:
        print(str(exc))
        return

    with SessionLocal() as session:
        model = session.scalar(
            select(UserModel).where(
                UserModel.email == email
            )
        )

        if model is None:
            service = UserService(
                SqlAlchemyUserRepository(
                    session
                )
            )

            user = service.create_user(
                email=email,
                full_name="OpsFlow Administrator",
                password=password,
                role=UserRole.ADMIN,
            )

            session.commit()

            print()
            print("Administrator created successfully.")
            print(f"ID:    {user.id}")
            print(f"Email: {user.email}")
            print(f"Role:  {user.role.value}")
            return

        model.hashed_password = hash_password(
            password
        )
        model.role = UserRole.ADMIN
        model.is_active = True
        model.updated_at = datetime.now(UTC)

        session.commit()

        print()
        print("Administrator recovered successfully.")
        print(f"ID:    {model.id}")
        print(f"Email: {model.email}")
        print(f"Role:  {model.role.value}")


if __name__ == "__main__":
    main()
