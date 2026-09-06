from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AuthSession:
    id: UUID

    user_id: UUID

    current_refresh_jti: UUID

    created_at: datetime

    expires_at: datetime

    last_refreshed_at: datetime | None = None

    revoked_at: datetime | None = None

    revocation_reason: str | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None