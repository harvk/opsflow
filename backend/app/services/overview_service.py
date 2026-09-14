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
        Return one internally consistent Overview snapshot.

        Summary values are calculated only from the Services
        and Incidents included in this response.
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

        service_responses = [
            ServiceResponse.model_validate(
                service
            )
            for service in services
        ]

        incident_responses = [
            IncidentResponse.model_validate(
                incident
            )
            for incident in incidents
        ]

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
            )
        )

    @staticmethod
    def _build_summary(
        *,
        services: list[Service],
        incidents: list[Incident],
    ) -> OverviewSummary:
        """
        Calculate Overview totals from the returned domain
        collections.

        A resolved incident is not active. A resolved incident
        marked customer-impacting is also excluded from the
        active customer-impacting count.
        """

        active_incidents = [
            incident
            for incident in incidents
            if (
                incident.status
                != IncidentStatus.RESOLVED
            )
        ]

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
                    len(
                        active_incidents
                    )
                ),
                customer_impacting_incidents=(
                    sum(
                        incident.customer_impacting
                        for incident
                        in active_incidents
                    )
                ),
            )
        )