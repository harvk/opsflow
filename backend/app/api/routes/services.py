from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.api.dependencies import ServiceServiceDependency, IncidentServiceDependency
from app.domain.service import ServiceStatus
from app.schemas.service import (
    ServiceCreate,
    ServiceResponse,
    ServiceUpdate,
)
from app.services.service_service import (
    ServiceNameConflictError,
    ServiceNotFoundError,
)
from app.schemas.incident import IncidentResponse

from app.services.incident_service import IncidentNotFoundError

from app.api.dependencies import get_incident_service


router = APIRouter()


@router.get(
    "",
    response_model=list[ServiceResponse],
)
def list_services(
    service_service: ServiceServiceDependency,
    search: Annotated[
        str | None,
        Query(
            description=(
                "Search services by name, owner, or description."
            ),
        ),
    ] = None,
    service_status: Annotated[
        ServiceStatus | None,
        Query(
            alias="status",
            description="Filter services by status.",
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description="Number of services to skip.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Maximum number of services to return."
            ),
        ),
    ] = 50,
) -> list[ServiceResponse]:
    services = service_service.list_services(
        search=search,
        status=service_status,
        offset=offset,
        limit=limit,
    )

    return [
        ServiceResponse.model_validate(service)
        for service in services
    ]


@router.get(
    "/{service_id}",
    response_model=ServiceResponse,
)
def get_service(
    service_id: UUID,
    service_service: ServiceServiceDependency,
) -> ServiceResponse:
    try:
        service = service_service.get_service(
            service_id
        )
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ServiceResponse.model_validate(
        service
    )
    
@router.get(
    "/{service_id}/incidents",
    response_model=list[IncidentResponse],
)
def list_service_incidents(
    service_id: UUID,
    incident_service: Annotated[
        IncidentServiceDependency,
        Depends(get_incident_service),
    ],
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
) -> list[IncidentResponse]:
    try:
        incidents = incident_service.list_for_service(
                service_id,
                offset=offset,
                limit=limit,
            )
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc)
        )

    return [
        IncidentResponse.model_validate(incident)
        for incident in incidents
    ]


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    payload: ServiceCreate,
    service_service: ServiceServiceDependency,
) -> ServiceResponse:
    try:
        service = service_service.create_service(
            payload
        )
    except ServiceNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ServiceResponse.model_validate(
        service
    )


@router.patch(
    "/{service_id}",
    response_model=ServiceResponse,
)
def update_service(
    service_id: UUID,
    payload: ServiceUpdate,
    service_service: ServiceServiceDependency,
) -> ServiceResponse:
    try:
        service = service_service.update_service(
            service_id,
            payload,
        )
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ServiceNameConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ServiceResponse.model_validate(
        service
    )


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_service(
    service_id: UUID,
    service_service: ServiceServiceDependency,
) -> None:
    try:
        service_service.delete_service(
            service_id
        )
    except ServiceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc