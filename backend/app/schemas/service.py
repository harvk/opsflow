from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.service import ServiceStatus


def to_camel(value: str) -> str:
    parts = value.split("_")

    return parts[0] + "".join(
        part.capitalize()
        for part in parts[1:]
    )


class ServiceSchema(BaseModel):
     model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class ServiceCreate(ServiceSchema):
    name: str
    owner: str
    status: ServiceStatus
    uptime: str

    latency_ms: int = Field(
        ge=0,
    )

    description: str
    region: str
    version: str
    last_deployed_at: datetime
    dependencies: list[str]

    @field_validator("name", "owner", "region", "version")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("must not contain only whitespace")

        return cleaned


class ServiceUpdate(ServiceSchema):
    name: str | None = None
    owner: str | None = None
    status: ServiceStatus | None = None
    uptime: str | None = None

    latency_ms: int | None = Field(
        default=None,
        ge=0,
    )

    description: str | None = None
    region: str | None = None
    version: str | None = None
    last_deployed_at: datetime | None = None
    dependencies: list[str] | None = None

    @field_validator("name", "owner", "region", "version")
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


class ServiceResponse(ServiceSchema):
    id: UUID
    name: str
    owner: str
    status: ServiceStatus
    uptime: str
    latency_ms: int
    description: str
    region: str
    version: str
    last_deployed_at: datetime
    dependencies: list[str]

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )
