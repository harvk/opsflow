from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status, Depends

from app.api.dependencies import (
    IncidentGatewayDependency,
    require_permission,
)

from app.domain.incident import IncidentSeverity, IncidentStatus
from app.domain.authorization import Permission

from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)


router = APIRouter()


@router.get(
    "",
    response_model=list[IncidentResponse],
    dependencies=[
        Depends(
            require_permission(
                Permission.SERVICE_READ
            )
        )
    ]
)
def list_incidents(
    incident_gateway: IncidentGatewayDependency,
    search: Annotated[
        str | None,
        Query(
            description=(
                "Search incidents by title, summary, or assignee."
            )
        ),
    ] = None,
    service_id: Annotated[
        UUID | None,
        Query(
            alias="serviceId",
            description=(
                "Filter incidents by Service ID."
            ),
        ),
    ] = None,
    severity: Annotated[
        IncidentSeverity | None,
        Query(
            description="Filter incidents by severity."
        ),
    ] = None,
    incident_status: Annotated[
        IncidentStatus | None,
        Query(
            alias="status",
            description="Filter incidents by status.",
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
    incidents = incident_gateway.list(
        search=search,
        service_id=service_id,
        severity=severity,
        status=incident_status,
        offset=offset,
        limit=limit,
    )

    return [
        IncidentResponse.model_validate(incident)
        for incident in incidents
    ]


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    dependencies=[
        Depends(
            require_permission(
                Permission.SERVICE_READ
            )
        )
    ]
)
def get_incident(
    incident_id: UUID,
    incident_gateway: IncidentGatewayDependency,
) -> IncidentResponse:
    try:
        incident = incident_gateway.get_by_id(
            incident_id
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IncidentResponse.model_validate(
        incident
    )


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_CREATE
            )
        )
    ]
)
def create_incident(
    payload: IncidentCreate,
    incident_gateway: IncidentGatewayDependency,
) -> IncidentResponse:
    try:
        incident = incident_gateway.create(
            payload
        )
    except IncidentServiceReferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IncidentResponse.model_validate(
        incident
    )


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_UPDATE
            )
        )
    ]
)
def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    incident_gateway: IncidentGatewayDependency,
) -> IncidentResponse:
    try:
        incident = incident_gateway.update(
            incident_id,
            payload,
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

    return IncidentResponse.model_validate(
        incident
    )


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_DELETE
            )
        )
    ]
)
def delete_incident(
    incident_id: UUID,
    incident_gateway: IncidentGatewayDependency,
) -> None:
    try:
        incident_gateway.delete(
            incident_id
        )
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
