from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from app.api.dependencies import (
    get_incident_service,
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
    RelatedServiceNotFoundError,
)
from app.services.incident_service import (
    IncidentService,
)

router = APIRouter()


IncidentServiceDependency = Annotated[
    IncidentService,
    Depends(get_incident_service),
]


@router.get(
    "",
    response_model=list[IncidentResponse],
)
def list_incidents(
    incident_service: IncidentServiceDependency,
    search: Annotated[
        str | None,
        Query(max_length=100),
    ] = None,
    status_filter: Annotated[
        IncidentStatus | None,
        Query(alias="status"),
    ] = None,
    severity: Annotated[
        IncidentSeverity | None,
        Query(),
    ] = None,
    service_id: Annotated[
        UUID | None,
        Query(alias="serviceId"),
    ] = None,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> list[IncidentResponse]:
    incidents = incident_service.list_incidents(
        search=search,
        status=status_filter,
        severity=severity,
        service_id=service_id,
        offset=offset,
        limit=limit,
    )

    return [IncidentResponse.model_validate(incident) for incident in incidents]


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def get_incident(
    incident_id: UUID,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = incident_service.get_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IncidentResponse.model_validate(incident)


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    payload: IncidentCreate,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = incident_service.create_incident(payload)
    except RelatedServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IncidentResponse.model_validate(incident)


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    incident_service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        incident = incident_service.update_incident(
            incident_id,
            payload,
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RelatedServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IncidentResponse.model_validate(incident)


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_incident(
    incident_id: UUID,
    incident_service: IncidentServiceDependency,
) -> Response:
    try:
        incident_service.delete_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
