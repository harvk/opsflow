from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)


class IncidentModel(Base):
    """
    SQLAlchemy representation Incident.

    Incident Management owns this table and its lifecycle.

    service_id is an external Service Catalog identifier. It
    deliberately has no foreign key or ORM relationship to a
    Service model owned by another service.
    """

    __tablename__ = "incidents"

    __table_args__ = (
        Index(
            "ix_incidents_service_status",
            "service_id",
            "status",
        ),
        Index(
            "ix_incidents_created_at",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    service_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    severity: Mapped[IncidentSeverity] = mapped_column(
        SqlEnum(
            IncidentSeverity,
            name="incident_severity",
            values_callable=lambda enum: [
                member.value
                for member in enum
            ],
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[IncidentStatus] = mapped_column(
        SqlEnum(
            IncidentStatus,
            name="incident_status",
            values_callable=lambda enum: [
                member.value
                for member in enum
            ],
        ),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    assignee: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        server_default=text(
            "'manual'"
        ),
    )

    customer_impacting: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text(
            "false"
        ),
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reported_by_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )