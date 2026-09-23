from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, status

from app.api.routes.incidents import (
    create_incident,
    delete_incident,
    get_incident,
    list_incidents,
    update_incident,
)
from app.api.routes.services import list_service_incidents
from app.domain.incident import IncidentSeverity
from app.domain.user import User, UserRole
from app.gateways.incident_gateway import (
    IncidentGateway,
    IncidentGatewayError,
    IncidentGatewayProtocolError,
    IncidentGatewayUnavailableError,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from app.services.service_service import (
    ServiceNotFoundError,
    ServiceService,
)

RouteCall = Callable[[IncidentGateway], object]


class RaisingIncidentGateway:
    def __init__(
        self,
        error: IncidentGatewayError,
    ) -> None:
        self.error = error

    def __getattr__(
        self,
        _name: str,
    ) -> Callable[..., object]:
        def raise_error(
            *_args: object,
            **_kwargs: object,
        ) -> object:
            raise self.error

        return raise_error


class ExistingServiceService:
    def get_service(
        self,
        _service_id: UUID,
    ) -> object:
        return object()


class MissingServiceService:
    def get_service(
        self,
        service_id: UUID,
    ) -> object:
        raise ServiceNotFoundError(
            f"Service {service_id} was not found."
        )


class RecordingIncidentGateway:
    def __init__(self) -> None:
        self.was_called = False

    def list_for_service(
        self,
        _service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[object]:
        self.was_called = True
        return []


def call_list(
    gateway: IncidentGateway,
) -> object:
    return list_incidents(
        incident_gateway=gateway,
        search=None,
        service_id=None,
        severity=None,
        incident_status=None,
        offset=0,
        limit=50,
    )


def call_get(
    gateway: IncidentGateway,
) -> object:
    return get_incident(
        incident_id=uuid4(),
        incident_gateway=gateway,
    )


def call_create(
    gateway: IncidentGateway,
) -> object:
    payload = IncidentCreate(
        title="Gateway failure test",
        service_id=uuid4(),
        severity=IncidentSeverity.SEV_2,
        summary="Exercise route error translation.",
        assignee="Platform Team",
    )

    now = datetime.now(UTC)
    current_user = User(
        id=uuid4(),
        email="operator@example.com",
        full_name="Gateway Route Test User",
        role=UserRole.OPERATOR,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    return create_incident(
        payload=payload,
        incident_gateway=gateway,
        current_user=current_user,
    )


def call_update(
    gateway: IncidentGateway,
) -> object:
    return update_incident(
        incident_id=uuid4(),
        payload=cast(
            IncidentUpdate,
            object(),
        ),
        incident_gateway=gateway,
    )


def call_delete(
    gateway: IncidentGateway,
) -> object:
    return delete_incident(
        incident_id=uuid4(),
        incident_gateway=gateway,
    )


def call_list_for_service(
    gateway: IncidentGateway,
) -> object:
    return list_service_incidents(
        service_id=uuid4(),
        incident_gateway=gateway,
        service_service=cast(
            ServiceService,
            ExistingServiceService(),
        ),
        offset=0,
        limit=50,
    )


@pytest.mark.parametrize(
    "call_route",
    [
        pytest.param(call_list, id="list"),
        pytest.param(call_get, id="get"),
        pytest.param(call_create, id="create"),
        pytest.param(call_update, id="update"),
        pytest.param(call_delete, id="delete"),
        pytest.param(
            call_list_for_service,
            id="list-for-service",
        ),
    ],
)
def test_routes_translate_gateway_protocol_errors(
    call_route: RouteCall,
) -> None:
    gateway = cast(
        IncidentGateway,
        RaisingIncidentGateway(
            IncidentGatewayProtocolError()
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        call_route(gateway)

    assert (
        exc_info.value.status_code
        == status.HTTP_502_BAD_GATEWAY
    )
    assert exc_info.value.detail == (
        "Incident service returned an invalid response."
    )


def test_route_translates_gateway_unavailable_error(
) -> None:
    gateway = cast(
        IncidentGateway,
        RaisingIncidentGateway(
            IncidentGatewayUnavailableError()
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        call_list(gateway)

    assert (
        exc_info.value.status_code
        == status.HTTP_503_SERVICE_UNAVAILABLE
    )
    assert exc_info.value.detail == (
        "Incident service is unavailable."
    )


def test_service_incidents_preserves_missing_service_404(
) -> None:
    service_id = uuid4()
    gateway = RecordingIncidentGateway()

    with pytest.raises(HTTPException) as exc_info:
        list_service_incidents(
            service_id=service_id,
            incident_gateway=cast(
                IncidentGateway,
                gateway,
            ),
            service_service=cast(
                ServiceService,
                MissingServiceService(),
            ),
            offset=0,
            limit=50,
        )

    assert (
        exc_info.value.status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert exc_info.value.detail == (
        f"Service {service_id} was not found."
    )
    assert gateway.was_called is False
