from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
)

from sqlalchemy.dialects.postgresql import (
    UUID as PGUUID,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base


class AuthSessionModel(Base):
    """
    Persistent server-side state for one authenticated
    refresh-token session.

    The row represents a refresh-token family.

    id:
        Stable session identifier. This will eventually be
        represented by the refresh JWT's `sid` claim.

    current_jti:
        Identifier of the one refresh JWT currently allowed
        to rotate this session.

    revoked_at:
        When non-null, the entire refresh-token family is
        invalid.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        primary_key=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    current_jti: Mapped[UUID] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    last_used_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    expires_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        index=True,
    )

    revoked_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
    )

    revocation_reason: Mapped[
        str | None
    ] = mapped_column(
        String(
            length=64
        ),
        nullable=True,
    )