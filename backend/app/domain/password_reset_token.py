from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime

from uuid import UUID


@dataclass(
    slots=True,
)
class PasswordResetToken:
    """
    Domain representation of one password-reset credential.

    token_digest:
        SHA-256 digest of the raw bearer credential.

    credential_fingerprint:
        binds this reset credential to the password hash that
        existed when the reset request was created.

    used_at:
        set when this exact credential successfully resets
        the password.

    invalidated_at:
        set when the credential is deliberately superseded
        or otherwise made unusable without being consumed.
    """

    id: UUID

    user_id: UUID

    token_digest: str

    credential_fingerprint: str

    created_at: datetime

    expires_at: datetime

    used_at: datetime | None = None

    invalidated_at: datetime | None = None

    @property
    def is_used(
        self,
    ) -> bool:
        return (
            self.used_at
            is not None
        )

    @property
    def is_invalidated(
        self,
    ) -> bool:
        return (
            self.invalidated_at
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

    def is_usable(
        self,
        *,
        now: datetime,
    ) -> bool:
        return (
            not self.is_used
            and not self.is_invalidated
            and not self.is_expired(
                now=now
            )
        )