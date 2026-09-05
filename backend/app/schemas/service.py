from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.domain.service import ServiceStatus


class ServiceSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ServiceCreate(ServiceSchema):
    name: str = Field(min_length=2, max_length=100)
    owner: str = Field(min_length=2, max_length=100)

    status: ServiceStatus = ServiceStatus.HEALTHY

    uptime: str = Field(
        default="100.00%",
        min_length=2,
        max_length=10,
    )

    latency_ms: int = Field(
        default=0,
        ge=0,
    )

    description: str = Field(
        default="",
        max_length=1000,
    )

    region: str = Field(
        default="us-east-1",
        min_length=2,
        max_length=50,
    )

    version: str = Field(
        default="1.0.0",
        min_length=1,
        max_length=50,
    )

    last_deployed_at: datetime | None = None

    dependencies: list[str] = Field(
        default_factory=list,
        max_length=50,
    )

    @field_validator("name", "owner", "region", "version")
    @classmethod
    def strip_required_strings(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("must not contain only whitespace")

        return cleaned


class ServiceUpdate(ServiceSchema):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    owner: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    status: ServiceStatus | None = None

    uptime: str | None = Field(
        default=None,
        min_length=2,
        max_length=10,
    )

    latency_ms: int | None = Field(
        default=None,
        ge=0,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    region: str | None = Field(
        default=None,
        min_length=2,
        max_length=50,
    )

    version: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    last_deployed_at: datetime | None = None

    dependencies: list[str] | None = Field(
        default=None,
        max_length=50,
    )

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
