from __future__ import annotations

from typing import (
    Final,
    Protocol,
)
from uuid import (
    UUID,
)

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.service import (
    Service,
    ServiceStatus,
)
from app.gateways.incident_gateway import (
    IncidentGatewayError,
)
from app.schemas.incident import (
    IncidentResponse,
)
from app.schemas.overview import (
    OverviewResponse,
    OverviewSummary,
)
from app.schemas.service import (
    ServiceResponse,
)

OVERVIEW_COLLECTION_LIMIT: Final[int] = 100


class ServiceLister(
    Protocol
):
    """
    Narrow Service Catalog capability required by composition.

    ServiceService satisfies this protocol without depending on
    a particular repository implementation.
    """

    def list_services(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]:
        ...


class IncidentLister(
    Protocol
):
    """
    Narrow Incident Management capability required by
    composition.

    IncidentGateway satisfies this protocol regardless of
    whether its active implementation is local or HTTP-based.
    """

    def list(
        self,
        *,
        search: str | None = None,
        service_id: UUID | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        ...


class OverviewService:
    """
    Compose Service Catalog and Incident Management data into
    one public Overview response.

    This service contains no FastAPI, SQLAlchemy, HTTP client,
    Docker, or frontend dependencies.
    """

    def __init__(
        self,
        *,
        service_service: ServiceLister,
        incident_gateway: IncidentLister,
    ) -> None:
        self._service_service = (
            service_service
        )

        self._incident_gateway = (
            incident_gateway
        )

    def get_overview(
        self,
    ) -> OverviewResponse:
        """
        Return one Overview snapshot.

        Service Catalog data is required because the Backend
        owns that data locally.

        Incident Management data is optional for this composed
        read. A known IncidentGateway failure produces an
        explicitly degraded response while preserving current
        Service Catalog information.
        """

        services = (
            self._service_service
            .list_services(
                search=None,
                status=None,
                offset=0,
                limit=(
                    OVERVIEW_COLLECTION_LIMIT
                ),
            )
        )

        incidents: (
            list[Incident]
            | None
        )

        try:
            incidents = (
                self._incident_gateway
                .list(
                    search=None,
                    service_id=None,
                    severity=None,
                    status=None,
                    offset=0,
                    limit=(
                        OVERVIEW_COLLECTION_LIMIT
                    ),
                )
            )

        except IncidentGatewayError:
            incidents = None

        service_responses = [
            ServiceResponse.model_validate(
                service
            )
            for service in services
        ]

        incident_responses = (
            []
            if incidents is None
            else [
                IncidentResponse.model_validate(
                    incident
                )
                for incident in incidents
            ]
        )

        summary = (
            self._build_summary(
                services=services,
                incidents=incidents,
            )
        )

        return (
            OverviewResponse(
                summary=summary,
                services=(
                    service_responses
                ),
                incidents=(
                    incident_responses
                ),
                incident_data_available=(
                    incidents
                    is not None
                ),
            )
        )

    @staticmethod
    def _build_summary(
        *,
        services: list[Service],
        incidents: (
            list[Incident]
            | None
        ),
    ) -> OverviewSummary:
        """
        Calculate Overview totals from the returned domain
        collections.

        Null incident counts mean Incident Management was
        unavailable. Numeric zero means Incident Management
        responded successfully and contained no matching
        active incidents.
        """

        active_incident_count: (
            int
            | None
        )

        customer_impacting_count: (
            int
            | None
        )

        if incidents is None:
            active_incident_count = None
            customer_impacting_count = None

        else:
            active_incidents = [
                incident
                for incident in incidents
                if (
                    incident.status
                    != IncidentStatus.RESOLVED
                )
            ]

            active_incident_count = (
                len(
                    active_incidents
                )
            )

            customer_impacting_count = (
                sum(
                    incident
                    .customer_impacting
                    for incident
                    in active_incidents
                )
            )

        return (
            OverviewSummary(
                total_services=(
                    len(
                        services
                    )
                ),
                healthy_services=(
                    sum(
                        service.status
                        == ServiceStatus.HEALTHY
                        for service in services
                    )
                ),
                degraded_services=(
                    sum(
                        service.status
                        == ServiceStatus.DEGRADED
                        for service in services
                    )
                ),
                critical_services=(
                    sum(
                        service.status
                        == ServiceStatus.CRITICAL
                        for service in services
                    )
                ),
                active_incidents=(
                    active_incident_count
                ),
                customer_impacting_incidents=(
                    customer_impacting_count
                ),
            )
        )