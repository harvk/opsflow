from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)
from pydantic.alias_generators import (
    to_camel,
)

from app.schemas.incident import (
    IncidentResponse,
)
from app.schemas.service import (
    ServiceResponse,
)


class OverviewSchema(
    BaseModel
):
    """
    Base configuration for public Overview API schemas.

    Python code uses snake_case field names while HTTP JSON
    responses use camelCase aliases.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class OverviewSummary(
    OverviewSchema
):
    """
    Aggregate operational counts calculated from the Service
    and Incident collections returned in the same response.
    """

    total_services: int
    healthy_services: int
    degraded_services: int
    critical_services: int
    active_incidents: int
    customer_impacting_incidents: int


class OverviewResponse(
    OverviewSchema
):
    """
    Composed public response for the OpsFlow Overview page.

    Service data remains owned by the Backend Service Catalog.
    Incident data remains owned by Incident Management and is
    obtained through IncidentGateway.
    """

    summary: OverviewSummary
    services: list[ServiceResponse]
    incidents: list[IncidentResponse]