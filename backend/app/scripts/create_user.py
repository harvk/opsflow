from getpass import getpass

from app.db.session import SessionLocal
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import (
    UserAlreadyExistsError,
    UserService,
)


def main() -> None:
    print("Create OpsFlow User")
    print("-------------------")

    email = input("Email: ").strip()
    full_name = input("Full name: ").strip()

    print()
    print("Available roles:")
    print("viewer")
    print("operator")
    print("admin")
    print()

    role_input = input(
        "Role [viewer]: "
    ).strip().lower()

    if not role_input:
        role_input = "viewer"

    try:
        role = UserRole(role_input)
    except ValueError:
        print(
            f"Invalid role: {role_input}"
        )
        return

    password = getpass(
        "Password: "
    )

    confirm_password = getpass(
        "Confirm password: "
    )

    if password != confirm_password:
        print(
            "Passwords do not match."
        )
        return

    if len(password) < 12:
        print(
            "Password must contain at least "
            "12 characters."
        )
        return

    with SessionLocal() as session:
        repository = (
            SqlAlchemyUserRepository(
                session
            )
        )

        service = UserService(
            repository
        )

        try:
            user = service.create_user(
                email=email,
                full_name=full_name,
                password=password,
                role=role,
            )

            session.commit()

        except UserAlreadyExistsError:
            session.rollback()

            print(
                "A user with that email "
                "already exists."
            )
            return

        except Exception:
            session.rollback()
            raise

    print()
    print("User created successfully.")
    print(f"ID:    {user.id}")
    print(f"Email: {user.email}")
    print(f"Role:  {user.role.value}")


if __name__ == "__main__":
    main()