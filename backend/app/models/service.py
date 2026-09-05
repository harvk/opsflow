from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.service import ServiceStatus


class ServiceModel(Base):
    __tablename__ = "services"

    __table_args__ = (
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_services_latency_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )

    owner: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    status: Mapped[ServiceStatus] = mapped_column(
        SqlEnum(
            ServiceStatus,
            name="service_status",
            values_callable=lambda enum: [
                member.value for member in enum
            ],
        ),
        nullable=False,
        index=True,
    )

    uptime: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    region: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    last_deployed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    dependencies: Mapped[list["ServiceDependencyModel"]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ServiceDependencyModel(Base):
    __tablename__ = "service_dependencies"

    service_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "services.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    dependency_name: Mapped[str] = mapped_column(
        String(120),
        primary_key=True,
    )

    service: Mapped[ServiceModel] = relationship(
        back_populates="dependencies",
    )