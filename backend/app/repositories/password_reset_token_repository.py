from __future__ import annotations

from datetime import (
    datetime,
)

from typing import (
    Protocol,
)

from uuid import (
    UUID,
)

from app.domain.password_reset_token import (
    PasswordResetToken,
)


class PasswordResetTokenRepository(
    Protocol
):
    """
    Persistence contract for one-time password-reset
    credentials.
    """

    def create(
        self,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        ...

    def get_by_digest_for_update(
        self,
        token_digest: str,
    ) -> PasswordResetToken | None:
        ...

    def mark_used(
        self,
        *,
        token_id: UUID,
        used_at: datetime,
    ) -> bool:
        ...

    def invalidate_active_for_user(
        self,
        *,
        user_id: UUID,
        invalidated_at: datetime,
        exclude_token_id: UUID | None = None,
    ) -> int:
        ...