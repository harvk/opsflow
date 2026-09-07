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

    Implementations may use PostgreSQL, another relational
    database, or another transactional persistence layer.

    The authentication service depends on this interface
    rather than directly on SQLAlchemy.
    """

    def create(
        self,
        auth_session: AuthSession,
    ) -> AuthSession:
        """
        Persist a newly-created authentication session.
        """
        ...

    def get_by_id(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        """
        Retrieve a session without acquiring a database row
        lock.
        """
        ...

    def get_by_id_for_update(
        self,
        session_id: UUID,
    ) -> AuthSession | None:
        """
        Retrieve and lock the session row.

        The SQLAlchemy implementation uses SELECT ... FOR
        UPDATE so refresh-token rotation can later occur
        atomically.
        """
        ...

    def update_current_token(
        self,
        *,
        session_id: UUID,
        current_jti: UUID,
        last_used_at: datetime,
    ) -> None:
        """
        Replace the currently-valid refresh-token identifier
        for a session.
        """
        ...

    def revoke(
        self,
        *,
        session_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> None:
        """
        Revoke one refresh-token session.
        """
        ...

    def revoke_all_for_user(
        self,
        *,
        user_id: UUID,
        revoked_at: datetime,
        reason: str,
    ) -> int:
        """
        Revoke every currently-active refresh session for a
        user.

        Returns the number of rows affected.
        """
        ...