from __future__ import annotations

from typing import (
    Annotated,
)
from uuid import (
    UUID,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from app.api.dependencies import (
    CurrentUser,
    IncidentGatewayDependency,
    require_permission,
)
from app.api.incident_gateway_errors import (
    incident_gateway_http_exception,
)
from app.api.task_dependencies import (
    IncidentNotificationServiceDependency,
)
from app.core.request_context import (
    get_request_id,
)
from app.domain.authorization import (
    Permission,
)
from app.domain.incident import (
    IncidentSeverity,
    IncidentStatus,
)
from app.gateways.incident_gateway import (
    IncidentGatewayError,
)
from app.messaging import (
    TaskPublishError,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.schemas.task import (
    TaskAcceptedResponse,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)

router = APIRouter()


# =========================================================
# LIST INCIDENTS
# =========================================================


@router.get(
    "",
    response_model=list[
        IncidentResponse
    ],
    dependencies=[
        Depends(
            require_permission(
                Permission.SERVICE_READ
            )
        )
    ],
)
def list_incidents(
    incident_gateway: IncidentGatewayDependency,
    search: Annotated[
        str | None,
        Query(
            description=(
                "Search incidents by title, "
                "summary, or assignee."
            )
        ),
    ] = None,
    service_id: Annotated[
        UUID | None,
        Query(
            alias="serviceId",
            description=(
                "Filter incidents by "
                "Service ID."
            ),
        ),
    ] = None,
    severity: Annotated[
        IncidentSeverity | None,
        Query(
            description=(
                "Filter incidents by severity."
            ),
        ),
    ] = None,
    incident_status: Annotated[
        IncidentStatus | None,
        Query(
            alias="status",
            description=(
                "Filter incidents by status."
            ),
        ),
    ] = None,
    offset: Annotated[
        int,
        Query(
            ge=0,
            description=(
                "Number of incidents to skip."
            ),
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description=(
                "Maximum number of incidents "
                "to return."
            ),
        ),
    ] = 50,
) -> list[
    IncidentResponse
]:
    try:
        incidents = (
            incident_gateway.list(
                search=search,
                service_id=(
                    service_id
                ),
                severity=severity,
                status=(
                    incident_status
                ),
                offset=offset,
                limit=limit,
            )
        )

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc

    return [
        IncidentResponse.model_validate(
            incident
        )
        for incident in incidents
    ]


# =========================================================
# GET INCIDENT
# =========================================================


@router.get(
    "/{incident_id}",
    response_model=(
        IncidentResponse
    ),
    dependencies=[
        Depends(
            require_permission(
                Permission.SERVICE_READ
            )
        )
    ],
)
def get_incident(
    incident_id: UUID,
    incident_gateway: IncidentGatewayDependency,
) -> IncidentResponse:
    try:
        incident = (
            incident_gateway.get_by_id(
                incident_id
            )
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_404_NOT_FOUND
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


# =========================================================
# REQUEST INCIDENT NOTIFICATION
# =========================================================


@router.post(
    "/{incident_id}/notification",
    response_model=(
        TaskAcceptedResponse
    ),
    status_code=(
        status.HTTP_202_ACCEPTED
    ),
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_UPDATE
            )
        )
    ],
)
def request_incident_notification(
    incident_id: UUID,
    notification_service: (
        IncidentNotificationServiceDependency
    ),
) -> TaskAcceptedResponse:
    """
    Request asynchronous notification processing for an
    existing Incident.

    The current request correlation ID is propagated into
    the task envelope.

    This endpoint does not mutate Incident persistence.
    """

    try:
        envelope = (
            notification_service
            .request_notification(
                incident_id=(
                    incident_id
                ),
                correlation_id=(
                    get_request_id()
                ),
            )
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_404_NOT_FOUND
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc

    except TaskPublishError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Asynchronous task publication "
                "is unavailable."
            ),
        ) from exc

    return TaskAcceptedResponse(
        taskId=(
            envelope.task_id
        ),
        taskType=(
            envelope.task_type
        ),
        correlationId=(
            envelope.correlation_id
        ),
        idempotencyKey=(
            envelope.idempotency_key
        ),
    )


# =========================================================
# CREATE INCIDENT
# =========================================================


@router.post(
    "",
    response_model=(
        IncidentResponse
    ),
    status_code=(
        status.HTTP_201_CREATED
    ),
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_CREATE
            )
        )
    ],
)
def create_incident(
    payload: IncidentCreate,
    incident_gateway: IncidentGatewayDependency,
    current_user: CurrentUser,
) -> IncidentResponse:
    stamped_payload = payload.model_copy(
        update={
            "reported_by_email": (
                current_user.email
            )
        }
    )

    try:
        incident = (
            incident_gateway.create(
                stamped_payload
            )
        )

    except IncidentServiceReferenceError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_404_NOT_FOUND
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


# =========================================================
# UPDATE INCIDENT
# =========================================================


@router.patch(
    "/{incident_id}",
    response_model=(
        IncidentResponse
    ),
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_UPDATE
            )
        )
    ],
)
def update_incident(
    incident_id: UUID,
    payload: IncidentUpdate,
    incident_gateway: IncidentGatewayDependency,
) -> IncidentResponse:
    try:
        incident = (
            incident_gateway.update(
                incident_id,
                payload,
            )
        )

    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_404_NOT_FOUND
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentServiceReferenceError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_400_BAD_REQUEST
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc

    return (
        IncidentResponse.model_validate(
            incident
        )
    )


# =========================================================
# DELETE INCIDENT
# =========================================================


@router.delete(
    "/{incident_id}",
    status_code=(
        status.HTTP_204_NO_CONTENT
    ),
    dependencies=[
        Depends(
            require_permission(
                Permission.INCIDENT_DELETE
            )
        )
    ],
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
            status_code=(
                status
                .HTTP_404_NOT_FOUND
            ),
            detail=str(
                exc
            ),
        ) from exc

    except IncidentGatewayError as exc:
        raise (
            incident_gateway_http_exception(
                exc
            )
        ) from exc
