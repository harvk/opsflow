from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)

if TYPE_CHECKING:
    from app.models.service import ServiceModel


class IncidentModel(Base):
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
        ForeignKey(
            "services.id",
            ondelete="CASCADE",
        ),
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

    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        server_default="manual",
    )

    customer_impacting: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
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

    service: Mapped["ServiceModel"] = relationship(
        "ServiceModel",
        back_populates="incidents",
    )