from uuid import (
    UUID,
)

from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies import (
    ServiceRepositoryDependency,
    require_incident_service_token,
)
from app.schemas.internal_service_catalog import (
    ServiceExistenceResponse,
)

router = (
    APIRouter(
        dependencies=[
            Depends(
                require_incident_service_token
            ),
        ],
    )
)


@router.get(
    "/{service_id}/exists",
    response_model=(
        ServiceExistenceResponse
    ),
)
def service_exists(
    service_id: UUID,
    service_repository: (
        ServiceRepositoryDependency
    ),
) -> ServiceExistenceResponse:
    service = (
        service_repository
        .get_by_id(
            service_id
        )
    )

    return (
        ServiceExistenceResponse(
            exists=(
                service is not None
            ),
        )
    )