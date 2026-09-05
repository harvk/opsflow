from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)


class IncidentSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class IncidentCreate(IncidentSchema):
    title: str = Field(
        min_length=3,
        max_length=200,
    )

    service_id: UUID

    severity: IncidentSeverity

    status: IncidentStatus = IncidentStatus.OPEN

    summary: str = Field(
        min_length=3,
        max_length=2000,
    )

    assignee: str = Field(
        default="Unassigned",
        min_length=2,
        max_length=100,
    )

    started_at: datetime | None = None

    @field_validator(
        "title",
        "summary",
        "assignee",
    )
    @classmethod
    def strip_required_strings(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("must not contain only whitespace")

        return cleaned


class IncidentUpdate(IncidentSchema):
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=200,
    )

    service_id: UUID | None = None

    severity: IncidentSeverity | None = None

    status: IncidentStatus | None = None

    summary: str | None = Field(
        default=None,
        min_length=3,
        max_length=2000,
    )

    assignee: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    started_at: datetime | None = None

    @field_validator(
        "title",
        "summary",
        "assignee",
    )
    @classmethod
    def strip_optional_strings(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            raise ValueError("must not contain only whitespace")

        return cleaned


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
