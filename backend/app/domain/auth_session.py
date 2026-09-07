from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(
    slots=True,
)
class AuthSession:
    """
    Server-side state for one refresh-token family.

    id:
        Stable session identifier represented by the `sid`
        claim in every refresh JWT belonging to this session.

    current_jti:
        Identifier of the one refresh JWT currently permitted
        to rotate this session.

    revoked_at:
        Non-null means the entire refresh-token family is no
        longer usable.
    """

    id: UUID
    user_id: UUID
    current_jti: UUID

    created_at: datetime
    last_used_at: datetime
    expires_at: datetime

    revoked_at: datetime | None = None

    revocation_reason: str | None = None

    @property
    def is_revoked(
        self,
    ) -> bool:
        return (
            self.revoked_at
            is not None
        )

    def is_expired(
        self,
        *,
        now: datetime,
    ) -> bool:
        return (
            now
            >= self.expires_at
        )