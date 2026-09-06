from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    decode_access_token,
    verify_password,
)
from app.domain.user import User
from app.repositories.user_repository import UserRepository


class AuthenticationError(Exception):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class InactiveUserError(AuthenticationError):
    pass


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository,
    ) -> None:
        self.repository = repository

    def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:
        normalized_email = email.strip().lower()

        auth_record = (
            self.repository.get_auth_record_by_email(
                normalized_email
            )
        )

        if auth_record is None:
            verify_password(
                password,
                DUMMY_PASSWORD_HASH,
            )

            raise InvalidCredentialsError(
                "Invalid credentials."
            )

        password_is_valid = verify_password(
            password,
            auth_record.hashed_password,
        )

        if not password_is_valid:
            raise InvalidCredentialsError(
                "Invalid credentials."
            )

        if not auth_record.user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )

        return auth_record.user

    def issue_access_token(
        self,
        user: User,
    ) -> str:
        if not user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )

        return create_access_token(
            user.id
        )

    def resolve_access_token(
        self,
        token: str,
    ) -> User:
        user_id = decode_access_token(
            token
        )

        user = self.repository.get_by_id(
            user_id
        )

        if user is None:
            raise InvalidCredentialsError(
                "The authenticated user no longer exists."
            )

        if not user.is_active:
            raise InactiveUserError(
                "The user account is inactive."
            )

        return user