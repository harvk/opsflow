from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies import (
    IncidentGatewayDependency,
    ServiceServiceDependency,
    require_permission,
)
from app.domain.authorization import (
    Permission,
)
from app.schemas.overview import (
    OverviewResponse,
)
from app.services.overview_service import (
    OverviewService,
)

router = APIRouter()


@router.get(
    "",
    response_model=OverviewResponse,
    dependencies=[
        Depends(
            require_permission(
                Permission.SERVICE_READ
            )
        )
    ],
)
def get_overview(
    service_service: (
        ServiceServiceDependency
    ),
    incident_gateway: (
        IncidentGatewayDependency
    ),
) -> OverviewResponse:
    """
    Compose Service Catalog and Incident Management data for
    the public OpsFlow Overview page.

    Known IncidentGateway failures are handled inside
    OverviewService and produce an explicitly degraded
    response. Authentication, authorization, Service Catalog,
    and unexpected application failures remain fail-closed.
    """

    overview_service = (
        OverviewService(
            service_service=(
                service_service
            ),
            incident_gateway=(
                incident_gateway
            ),
        )
    )

    return (
        overview_service
        .get_overview()
    )