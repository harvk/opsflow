from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
    uuid4,
)

import pytest

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
    IncidentGatewayUnavailableError,
)
from app.services.overview_service import (
    OVERVIEW_COLLECTION_LIMIT,
    OverviewService,
)

NOW = datetime(
    2026,
    9,
    14,
    12,
    0,
    tzinfo=UTC,
)


class StubServiceLister:
    def __init__(
        self,
        services: list[Service],
    ) -> None:
        self._services = services
        self.received_offset: int | None = None
        self.received_limit: int | None = None

    def list_services(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]:
        assert search is None
        assert status is None

        self.received_offset = offset
        self.received_limit = limit

        return list(
            self._services
        )


class StubIncidentLister:
    def __init__(
        self,
        incidents: list[Incident],
    ) -> None:
        self._incidents = incidents
        self.received_offset: int | None = None
        self.received_limit: int | None = None

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
        assert search is None
        assert service_id is None
        assert severity is None
        assert status is None

        self.received_offset = offset
        self.received_limit = limit

        return list(
            self._incidents
        )


class FailingIncidentLister(
    StubIncidentLister
):
    def __init__(
        self,
        error: Exception,
    ) -> None:
        super().__init__(
            []
        )

        self._error = error

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
        assert search is None
        assert service_id is None
        assert severity is None
        assert status is None

        self.received_offset = offset
        self.received_limit = limit

        raise self._error


def build_service(
    status: ServiceStatus,
) -> Service:
    return (
        Service(
            id=uuid4(),
            name=(
                f"{status.value} Service"
            ),
            owner="Platform",
            status=status,
            uptime="99.99%",
            latency_ms=100,
            description=(
                "Overview composition test service."
            ),
            region="us-east-1",
            version="1.0.0",
            last_deployed_at=NOW,
            dependencies=[],
            incidents=[],
        )
    )


def build_incident(
    *,
    status: IncidentStatus,
    customer_impacting: bool,
) -> Incident:
    return (
        Incident(
            id=uuid4(),
            title=(
                f"{status.value} incident"
            ),
            service_id=uuid4(),
            severity=(
                IncidentSeverity.SEV_2
            ),
            status=status,
            summary=(
                "Overview composition test incident."
            ),
            assignee="Platform Team",
            started_at=NOW,
            resolved_at=(
                NOW
                if (
                    status
                    == IncidentStatus.RESOLVED
                )
                else None
            ),
            created_at=NOW,
            updated_at=NOW,
            source="monitoring",
            customer_impacting=(
                customer_impacting
            ),
            acknowledged_at=None,
        )
    )


def build_overview_service(
) -> tuple[
    OverviewService,
    StubServiceLister,
    StubIncidentLister,
]:
    service_lister = (
        StubServiceLister(
            [
                build_service(
                    ServiceStatus.HEALTHY
                ),
                build_service(
                    ServiceStatus.HEALTHY
                ),
                build_service(
                    ServiceStatus.DEGRADED
                ),
                build_service(
                    ServiceStatus.CRITICAL
                ),
            ]
        )
    )

    incident_lister = (
        StubIncidentLister(
            [
                build_incident(
                    status=(
                        IncidentStatus.OPEN
                    ),
                    customer_impacting=True,
                ),
                build_incident(
                    status=(
                        IncidentStatus.INVESTIGATING
                    ),
                    customer_impacting=False,
                ),
                build_incident(
                    status=(
                        IncidentStatus.MONITORING
                    ),
                    customer_impacting=True,
                ),
                build_incident(
                    status=(
                        IncidentStatus.RESOLVED
                    ),
                    customer_impacting=True,
                ),
            ]
        )
    )

    overview_service = (
        OverviewService(
            service_service=(
                service_lister
            ),
            incident_gateway=(
                incident_lister
            ),
        )
    )

    return (
        overview_service,
        service_lister,
        incident_lister,
    )


def test_get_overview_composes_collections_and_summary(
) -> None:
    (
        overview_service,
        service_lister,
        incident_lister,
    ) = build_overview_service()

    response = (
        overview_service
        .get_overview()
    )

    assert (
        response
        .summary
        .total_services
        == 4
    )

    assert (
        response
        .summary
        .healthy_services
        == 2
    )

    assert (
        response
        .summary
        .degraded_services
        == 1
    )

    assert (
        response
        .summary
        .critical_services
        == 1
    )

    assert (
        response
        .summary
        .active_incidents
        == 3
    )

    assert (
        response
        .summary
        .customer_impacting_incidents
        == 2
    )

    assert len(
        response.services
    ) == 4

    assert len(
        response.incidents
    ) == 4

    assert (
        response
        .incident_data_available
        is True
    )

    assert (
        service_lister
        .received_offset
        == 0
    )

    assert (
        service_lister
        .received_limit
        == OVERVIEW_COLLECTION_LIMIT
    )

    assert (
        incident_lister
        .received_offset
        == 0
    )

    assert (
        incident_lister
        .received_limit
        == OVERVIEW_COLLECTION_LIMIT
    )


def test_get_overview_serializes_summary_as_camel_case(
) -> None:
    (
        overview_service,
        _,
        _,
    ) = build_overview_service()

    response = (
        overview_service
        .get_overview()
    )

    payload = (
        response.model_dump(
            mode="json",
            by_alias=True,
        )
    )

    assert payload[
        "incidentDataAvailable"
    ] is True

    assert (
        "incident_data_available"
        not in payload
    )

    summary = payload[
        "summary"
    ]

    assert summary[
        "totalServices"
    ] == 4

    assert summary[
        "healthyServices"
    ] == 2

    assert summary[
        "customerImpactingIncidents"
    ] == 2

    assert (
        "total_services"
        not in summary
    )

    assert (
        "customer_impacting_incidents"
        not in summary
    )

    first_service = payload[
        "services"
    ][0]

    assert "latencyMs" in (
        first_service
    )

    assert "lastDeployedAt" in (
        first_service
    )

    first_incident = payload[
        "incidents"
    ][0]

    assert "serviceId" in (
        first_incident
    )

    assert "customerImpacting" in (
        first_incident
    )


def test_get_overview_preserves_service_data_when_incidents_are_unavailable(
) -> None:
    service_lister = (
        StubServiceLister(
            [
                build_service(
                    ServiceStatus.HEALTHY
                ),
                build_service(
                    ServiceStatus.DEGRADED
                ),
            ]
        )
    )

    incident_lister = (
        FailingIncidentLister(
            IncidentGatewayUnavailableError(
                "Incident Management unavailable."
            )
        )
    )

    overview_service = (
        OverviewService(
            service_service=(
                service_lister
            ),
            incident_gateway=(
                incident_lister
            ),
        )
    )

    response = (
        overview_service
        .get_overview()
    )

    assert (
        response
        .incident_data_available
        is False
    )

    assert (
        response.incidents
        == []
    )

    assert (
        response
        .summary
        .total_services
        == 2
    )

    assert (
        response
        .summary
        .healthy_services
        == 1
    )

    assert (
        response
        .summary
        .degraded_services
        == 1
    )

    assert (
        response
        .summary
        .critical_services
        == 0
    )

    assert (
        response
        .summary
        .active_incidents
        is None
    )

    assert (
        response
        .summary
        .customer_impacting_incidents
        is None
    )

    assert len(
        response.services
    ) == 2

    assert (
        service_lister
        .received_limit
        == OVERVIEW_COLLECTION_LIMIT
    )

    assert (
        incident_lister
        .received_limit
        == OVERVIEW_COLLECTION_LIMIT
    )

    payload = (
        response.model_dump(
            mode="json",
            by_alias=True,
        )
    )

    assert payload[
        "incidentDataAvailable"
    ] is False

    assert payload[
        "summary"
    ][
        "activeIncidents"
    ] is None

    assert payload[
        "summary"
    ][
        "customerImpactingIncidents"
    ] is None


def test_get_overview_does_not_hide_unexpected_incident_errors(
) -> None:
    service_lister = (
        StubServiceLister(
            [
                build_service(
                    ServiceStatus.HEALTHY
                )
            ]
        )
    )

    incident_lister = (
        FailingIncidentLister(
            RuntimeError(
                "Unexpected incident failure."
            )
        )
    )

    overview_service = (
        OverviewService(
            service_service=(
                service_lister
            ),
            incident_gateway=(
                incident_lister
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Unexpected incident failure"
        ),
    ):
        (
            overview_service
            .get_overview()
        )