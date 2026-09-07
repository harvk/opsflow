from __future__ import annotations

from datetime import datetime

from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)

from sqlalchemy.dialects.postgresql import (
    UUID as PGUUID,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import (
    Base,
)


class PasswordResetTokenModel(
    Base
):
    """
    Persistent password-recovery credential.

    The raw bearer token is deliberately NOT stored.
    """

    __tablename__ = (
        "password_reset_tokens"
    )

    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name=(
                "uq_password_reset_tokens_"
                "token_digest"
            ),
        ),
        Index(
            "ix_password_reset_tokens_user_id",
            "user_id",
        ),
        Index(
            "ix_password_reset_tokens_expires_at",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = (
        mapped_column(
            PGUUID(
                as_uuid=True
            ),
            primary_key=True,
        )
    )

    user_id: Mapped[UUID] = (
        mapped_column(
            PGUUID(
                as_uuid=True
            ),
            ForeignKey(
                "users.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        )
    )

    token_digest: Mapped[str] = (
        mapped_column(
            String(
                length=64
            ),
            nullable=False,
        )
    )

    credential_fingerprint: Mapped[str] = (
        mapped_column(
            String(
                length=64
            ),
            nullable=False,
        )
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime(
                timezone=True
            ),
            nullable=False,
        )
    )

    expires_at: Mapped[datetime] = (
        mapped_column(
            DateTime(
                timezone=True
            ),
            nullable=False,
        )
    )

    used_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
    )

    invalidated_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
    )