from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.auth_session import (
    AuthSession,
)


class AuthSessionRepository(ABC):
    @abstractmethod
    def create(
        self,
        session: AuthSession,
    ) -> AuthSession:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(
        self,
        session_id: UUID,
        *,
        for_update: bool = False,
    ) -> AuthSession | None:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        session: AuthSession,
    ) -> AuthSession:
        raise NotImplementedError