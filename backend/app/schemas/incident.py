from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)


def to_camel(value: str) -> str:
    parts = value.split("_")

    return parts[0] + "".join(
        part.capitalize()
        for part in parts[1:]
    )


class IncidentSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class IncidentCreate(IncidentSchema):
    title: str = Field(
        min_length=1,
        max_length=200,
    )

    service_id: UUID

    severity: IncidentSeverity

    status: IncidentStatus = (
        IncidentStatus.OPEN
    )

    summary: str = Field(
        min_length=1,
        max_length=2000,
    )

    assignee: str = Field(
        min_length=1,
        max_length=120,
    )

    started_at: datetime | None = None


class IncidentUpdate(IncidentSchema):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    service_id: UUID | None = None

    severity: IncidentSeverity | None = None

    status: IncidentStatus | None = None

    summary: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
    )

    assignee: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    started_at: datetime | None = None


class IncidentResponse(IncidentSchema):
    id: UUID
    title: str
    service_id: UUID
    severity: IncidentSeverity
    status: IncidentStatus
    summary: str
    assignee: str
    started_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )