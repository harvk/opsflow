from __future__ import annotations

from datetime import datetime

from typing import Protocol

from uuid import UUID

from app.domain.password_reset_token import (
    PasswordResetToken,
)


class PasswordResetTokenRepository(
    Protocol
):
    """
    Persistence contract for password-reset credentials.

    Transaction ownership remains outside the repository.
    Implementations may flush but must not independently
    commit request transactions.
    """

    def create(
        self,
        reset_token: PasswordResetToken,
    ) -> PasswordResetToken:
        ...

    def get_by_id(
        self,
        token_id: UUID,
    ) -> PasswordResetToken | None:
        ...

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
        """
        Retrieve and lock one reset-token row.

        The lock prevents two concurrent requests from
        successfully consuming the same single-use token.
        """

        ...

    def mark_used(
        self,
        *,
        token_id: UUID,
        used_at: datetime,
    ) -> bool:
        """
        Mark an otherwise-active reset token as consumed.

        Returns True only when the update actually occurred.
        """

        ...

    def invalidate_active_for_user(
        self,
        *,
        user_id: UUID,
        invalidated_at: datetime,
        exclude_token_id: UUID | None = None,
    ) -> int:
        """
        Invalidate outstanding, unconsumed reset credentials
        belonging to the user.

        Returns the number of rows affected.
        """

        ...