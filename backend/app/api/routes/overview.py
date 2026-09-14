from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies import (
    IncidentGatewayDependency,
    ServiceServiceDependency,
    require_permission,
)
from app.api.incident_gateway_errors import (
    incident_gateway_http_exception,
)
from app.domain.authorization import (
    Permission,
)
from app.gateways.incident_gateway import (
    IncidentGatewayError,
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

    try:
        return (
            overview_service
            .get_overview()
        )

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc