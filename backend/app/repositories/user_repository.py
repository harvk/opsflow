from typing import Protocol
from uuid import UUID

from app.domain.user import User, UserAuthRecord, UserRole


class UserRepository(Protocol):
    def add(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.VIEWER,
        is_active: bool = True,
    ) -> User:
        ...

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        ...

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        ...

    def get_auth_record_by_email(
        self,
        email: str,
    ) -> UserAuthRecord | None:
        ...
        
    def update_password_hash_if_current(
        self,
        *,
        user_id: UUID,
        expected_hashed_password: str,
        new_hashed_password: str,
    ) -> bool:
        """
        Atomically replace a password hash only when the stored
        hash still equals expected_hashed_password.

        Returns True when exactly one user was updated.

        Returns False when the password changed between the
        earlier credential read and this update.
        """

        ...