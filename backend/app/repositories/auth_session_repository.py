from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.auth_session import (
    AuthSession,
)


class AuthSessionRepository(
    Protocol
):
    """
    Persistence contract for server-side authentication
    sessions.
    """

    def create(
        self,
        auth_session: AuthSession,
    ) -> AuthSession:
        ...

    def get_by_id(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        ...

    def get_by_id_for_update(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        ...

    def update_current_token(
        self,
        *,
        session_id: UUID,
        current_jti: UUID,
        last_used_at: datetime,
    ) -> None:
        ...

    def revoke(
        self,
        *,
        session_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        ...

    def revoke_all_for_user(
        self,
        *,
        user_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        ...

    def delete_expired_before(
        self,
        *,
        cutoff: datetime,
    ) -> int:
        """
        Delete sessions whose absolute expiration predates
        the supplied retention cutoff.
        """
        ...