from __future__ import annotations

from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from uuid import (
    UUID,
)


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetToken:
    """
    Persisted password-reset credential metadata.

    The raw bearer credential never appears in this object.

    token_digest:
        SHA-256 digest used to locate the credential.

    credential_fingerprint:
        Binds the credential to the password hash that
        existed when the reset was requested.
    """

    id: UUID

    user_id: UUID

    token_digest: str

    credential_fingerprint: str

    created_at: datetime

    expires_at: datetime

    used_at: datetime | None

    invalidated_at: datetime | None