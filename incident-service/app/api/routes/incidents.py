from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    status,
)

from app.api.dependencies import (
    IncidentReadPrincipal,
    IncidentServiceDependency,
    IncidentWritePrincipal,
)
from app.core.request_context import (
    get_request_id,
)
from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.services.exceptions import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
    ServiceCatalogUnavailableError,
)

router = APIRouter()


@router.get(
    "",
    response_model=list[IncidentResponse],
)
def list_incidents(
    _service_principal: IncidentReadPrincipal,
    incident_service: IncidentServiceDependency,
    search: Annotated[
        str | None,
        Query(
            description=(
                "Search incidents by title, summary, "
                "or assignee."
            ),
        ),
    ] = None,
    service_id: Annotated[
        UUID | None,
        Query(
            alias="serviceId",
            description="Filter by Service ID.",
        ),
    ] = None,
    severity: Annotated[
        IncidentSeverity | None,
        Query(
            description="Filter by severity.",
        ),
    ] = None,
    incident_status: Annotated[
        IncidentStatus | None,
        Query(
            alias="status",
            description="Filter by lifecycle status.",
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of incidents to skip.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Maximum number of incidents to return."
            ),
        ),
    ] = 50,
) -> list[IncidentResponse]:
    incidents = (
        incident_service.list(
            search=search,
            service_id=service_id,
            severity=severity,
            status=incident_status,
            offset=offset,
            limit=limit,
        )
    )

    return [
        IncidentResponse.model_validate(
            incident
        )
        for incident in incidents
    ]


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def get_incident(
    incident_id: UUID,
    _service_principal: IncidentReadPrincipal,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = (
            incident_service.get_by_id(
                incident_id
            )
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    payload: IncidentCreate,
    _service_principal: IncidentWritePrincipal,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = (
            incident_service.create(
                payload,
                correlation_id=(
                    get_request_id()
                ),
            )
        )

    except IncidentServiceReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ServiceCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    _service_principal: IncidentWritePrincipal,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = (
            incident_service.update(
                incident_id,
                payload,
            )
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except IncidentServiceReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except ServiceCatalogUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_incident(
    incident_id: UUID,
    _service_principal: IncidentWritePrincipal,
    incident_service: IncidentServiceDependency,
) -> None:
    try:
        incident_service.delete(
            incident_id
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
