from app.core.security import hash_password
from app.domain.user import User, UserRole
from app.repositories.user_repository import UserRepository


class UserAlreadyExistsError(ValueError):
    pass


class UserService:
    def __init__(
        self,
        repository: UserRepository,
    ) -> None:
        self.repository = repository

    def create_user(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        role: UserRole = UserRole.VIEWER,
    ) -> User:
        normalized_email = email.strip().lower()
        normalized_name = full_name.strip()

        existing_user = self.repository.get_by_email(
            normalized_email
        )

        if existing_user is not None:
            raise UserAlreadyExistsError(
                "A user with that email already exists."
            )

        hashed_password = hash_password(password)

        return self.repository.add(
            email=normalized_email,
            full_name=normalized_name,
            hashed_password=hashed_password,
            role=role,
        )