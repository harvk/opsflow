from __future__ import annotations

from datetime import (
    datetime,
)
from uuid import (
    UUID,
)

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
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


class IncidentTaskCompletionOutboxModel(
    Base
):
    __tablename__ = (
        "incident_task_completion_outbox"
    )

    __table_args__ = (
        CheckConstraint(
            (
                "publication_status IN "
                "('PENDING', 'PUBLISHED')"
            ),
            name=(
                "ck_incident_completion_outbox_"
                "publication_status"
            ),
        ),
        CheckConstraint(
            (
                "status IN "
                "('Open', 'Investigating', "
                "'Monitoring', 'Resolved')"
            ),
            name=(
                "ck_incident_completion_outbox_"
                "status"
            ),
        ),
        Index(
            "ix_incident_completion_outbox_pending",
            "publication_status",
            "created_at",
        ),
        Index(
            "ix_incident_completion_outbox_incident_id",
            "incident_id",
        ),
        Index(
            "ix_incident_completion_outbox_correlation_id",
            "correlation_id",
        ),
    )

    id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        primary_key=True,
    )

    event_id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        nullable=False,
        unique=True,
    )

    incident_id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        nullable=False,
    )

    task_id: Mapped[
        UUID
    ] = mapped_column(
        PGUUID(
            as_uuid=True
        ),
        nullable=False,
        unique=True,
    )

    correlation_id: Mapped[
        str
    ] = mapped_column(
        String(
            128
        ),
        nullable=False,
    )

    schema_version: Mapped[
        str
    ] = mapped_column(
        String(
            16
        ),
        nullable=False,
    )

    event_type: Mapped[
        str
    ] = mapped_column(
        String(
            120
        ),
        nullable=False,
    )

    status: Mapped[
        str
    ] = mapped_column(
        String(
            32
        ),
        nullable=False,
    )

    acknowledged_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
    )

    occurred_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    publication_status: Mapped[
        str
    ] = mapped_column(
        String(
            24
        ),
        nullable=False,
        server_default=(
            "PENDING"
        ),
    )

    publish_attempts: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
        server_default=text(
            "0"
        ),
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=False,
    )

    published_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(
            timezone=True
        ),
        nullable=True,
    )

    last_error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )
