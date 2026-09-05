from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Text,
    Boolean,
    Index,
    text
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)

from typing import TYPE_CHECKING

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

    service: Mapped["ServiceModel"] = relationship(
        "ServiceModel",
        back_populates="incidents",
    )

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