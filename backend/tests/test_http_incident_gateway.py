from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.incident_gateway import (
    IncidentGatewayProtocolError,
    IncidentGatewayUnavailableError,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)
from app.services.incident_service import (
    IncidentNotFoundError,
    IncidentServiceReferenceError,
)

INCIDENT_ID = UUID(
    "11111111-1111-4111-8111-111111111111"
)

SERVICE_ID = UUID(
    "22222222-2222-4222-8222-222222222222"
)

INCIDENT_SERVICE_URL = (
    "http://incident-service:8000/api/v1"
)

INTERNAL_TOKEN = (
    "test-internal-token-that-is-at-least-32-characters"
)

INCIDENT_RESPONSE = {
    "id": str(INCIDENT_ID),
    "title": "Checkout latency",
    "serviceId": str(SERVICE_ID),
    "severity": "SEV-2",
    "status": "Investigating",
    "summary": "Checkout latency is elevated.",
    "assignee": "Platform Team",
    "source": "monitoring",
    "customerImpacting": True,
    "acknowledgedAt": (
        "2026-09-14T01:05:00Z"
    ),
    "startedAt": (
        "2026-09-14T01:00:00Z"
    ),
    "resolvedAt": None,
    "createdAt": (
        "2026-09-14T01:01:00Z"
    ),
    "updatedAt": (
        "2026-09-14T01:05:00Z"
    ),
}


def build_gateway(
    handler: Callable[
        [httpx.Request],
        httpx.Response,
    ],
) -> tuple[
    HttpIncidentGateway,
    httpx.Client,
]:
    client = httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )

    gateway = HttpIncidentGateway(
        client=client,
        incident_service_url=(
            INCIDENT_SERVICE_URL
        ),
        internal_token=(
            INTERNAL_TOKEN
        ),
    )

    return gateway, client


def assert_internal_authentication(
    request: httpx.Request,
) -> None:
    assert (
        request.headers[
            "X-OpsFlow-Internal-Token"
        ]
        == INTERNAL_TOKEN
    )


@pytest.mark.parametrize(
    "source",
    [
        "",
        "x" * 81,
    ],
)
def test_core_source_validation_matches_remote_contract(
    source: str,
) -> None:
    with pytest.raises(
        ValidationError
    ):
        IncidentCreate(
            title="Checkout latency",
            service_id=SERVICE_ID,
            severity=(
                IncidentSeverity.SEV_2
            ),
            summary=(
                "Checkout latency is elevated."
            ),
            assignee="Platform Team",
            source=source,
        )


def test_list_translates_filters_and_response(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url.path == (
            "/api/v1/incidents"
        )

        assert dict(
            request.url.params
        ) == {
            "offset": "10",
            "limit": "25",
            "search": "checkout",
            "serviceId": str(
                SERVICE_ID
            ),
            "severity": "SEV-2",
            "status": "Investigating",
        }

        assert_internal_authentication(
            request
        )

        return httpx.Response(
            200,
            json=[
                INCIDENT_RESPONSE
            ],
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        incidents = gateway.list(
            search="checkout",
            service_id=SERVICE_ID,
            severity=(
                IncidentSeverity.SEV_2
            ),
            status=(
                IncidentStatus
                .INVESTIGATING
            ),
            offset=10,
            limit=25,
        )

    finally:
        client.close()

    assert len(incidents) == 1

    assert isinstance(
        incidents[0],
        Incident,
    )

    assert (
        incidents[0].id
        == INCIDENT_ID
    )

    assert (
        incidents[0].service_id
        == SERVICE_ID
    )

    assert (
        incidents[0].severity
        is IncidentSeverity.SEV_2
    )

    assert (
        incidents[0].status
        is IncidentStatus.INVESTIGATING
    )


def test_list_omits_unused_optional_filters(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert dict(
            request.url.params
        ) == {
            "offset": "0",
            "limit": "50",
        }

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        assert gateway.list() == []

    finally:
        client.close()


def test_list_for_service_uses_service_id_filter(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == (
            "/api/v1/incidents"
        )

        assert dict(
            request.url.params
        ) == {
            "offset": "5",
            "limit": "10",
            "serviceId": str(
                SERVICE_ID
            ),
        }

        return httpx.Response(
            200,
            json=[
                INCIDENT_RESPONSE
            ],
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        incidents = (
            gateway.list_for_service(
                SERVICE_ID,
                offset=5,
                limit=10,
            )
        )

    finally:
        client.close()

    assert [
        incident.id
        for incident in incidents
    ] == [
        INCIDENT_ID
    ]


def test_get_by_id_returns_domain_incident(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"

        assert request.url.path == (
            f"/api/v1/incidents/"
            f"{INCIDENT_ID}"
        )

        assert_internal_authentication(
            request
        )

        return httpx.Response(
            200,
            json=INCIDENT_RESPONSE,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        incident = gateway.get_by_id(
            INCIDENT_ID
        )

    finally:
        client.close()

    assert isinstance(
        incident,
        Incident,
    )

    assert incident.id == INCIDENT_ID


def test_get_by_id_translates_not_found(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "detail": (
                    "Incident was not found."
                )
            },
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentNotFoundError,
            match=(
                "Incident was not found"
            ),
        ):
            gateway.get_by_id(
                INCIDENT_ID
            )

    finally:
        client.close()


def test_create_sends_camel_case_payload(
) -> None:
    payload = IncidentCreate(
        title="Checkout latency",
        service_id=SERVICE_ID,
        severity=(
            IncidentSeverity.SEV_2
        ),
        status=(
            IncidentStatus
            .INVESTIGATING
        ),
        summary=(
            "Checkout latency is elevated."
        ),
        assignee="Platform Team",
        source="monitoring",
        customer_impacting=True,
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"

        assert request.url.path == (
            "/api/v1/incidents"
        )

        assert_internal_authentication(
            request
        )

        request_payload = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        assert (
            request_payload[
                "serviceId"
            ]
            == str(SERVICE_ID)
        )

        assert (
            request_payload[
                "customerImpacting"
            ]
            is True
        )

        assert (
            "service_id"
            not in request_payload
        )

        assert (
            "customer_impacting"
            not in request_payload
        )

        return httpx.Response(
            201,
            json=INCIDENT_RESPONSE,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        incident = gateway.create(
            payload
        )

    finally:
        client.close()

    assert incident.id == INCIDENT_ID


def test_create_translates_missing_service(
) -> None:
    payload = IncidentCreate(
        title="Checkout latency",
        service_id=SERVICE_ID,
        severity=(
            IncidentSeverity.SEV_2
        ),
        summary=(
            "Checkout latency is elevated."
        ),
        assignee="Platform Team",
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "detail": (
                    "Referenced service "
                    "was not found."
                )
            },
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentServiceReferenceError,
            match=(
                "Referenced service "
                "was not found"
            ),
        ):
            gateway.create(
                payload
            )

    finally:
        client.close()


def test_update_preserves_explicit_null(
) -> None:
    payload = IncidentUpdate(
        resolved_at=None,
        acknowledged_at=None,
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        request_payload = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        assert request_payload == {
            "acknowledgedAt": None,
            "resolvedAt": None,
        }

        return httpx.Response(
            200,
            json=INCIDENT_RESPONSE,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        incident = gateway.update(
            INCIDENT_ID,
            payload,
        )

    finally:
        client.close()

    assert incident.id == INCIDENT_ID


def test_update_translates_service_reference_error(
) -> None:
    payload = IncidentUpdate(
        service_id=SERVICE_ID
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "detail": (
                    "Referenced service was not found."
                )
            },
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentServiceReferenceError,
            match=(
                "Referenced service was not found"
            ),
        ):
            gateway.update(
                INCIDENT_ID,
                payload,
            )

    finally:
        client.close()


def test_delete_accepts_no_content(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == (
            "DELETE"
        )

        assert request.url.path == (
            f"/api/v1/incidents/"
            f"{INCIDENT_ID}"
        )

        assert_internal_authentication(
            request
        )

        return httpx.Response(
            204
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        assert (
            gateway.delete(
                INCIDENT_ID
            )
            is None
        )

    finally:
        client.close()


def test_timeout_becomes_unavailable_error(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "timed out",
            request=request,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError,
            match="timed out",
        ):
            gateway.list()

    finally:
        client.close()


def test_connection_failure_does_not_disclose_token(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError
        ) as captured_error:
            gateway.list()

    finally:
        client.close()

    assert INTERNAL_TOKEN not in str(
        captured_error.value
    )

    assert (
        captured_error
        .value
        .__cause__
        is None
    )


def test_server_error_becomes_unavailable_error(
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            503,
            json={
                "detail": (
                    "Internal dependency "
                    "unavailable."
                )
            },
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError,
            match=(
                "Incident Service "
                "is unavailable"
            ),
        ):
            gateway.list()

    finally:
        client.close()


@pytest.mark.parametrize(
    "status_code",
    [
        401,
        403,
        409,
        422,
    ],
)
def test_unexpected_client_status_becomes_protocol_error(
    status_code: int,
) -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "detail": (
                    "Unexpected response."
                )
            },
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentGatewayProtocolError,
            match=(
                "unexpected response"
            ),
        ):
            gateway.list()

    finally:
        client.close()


def test_invalid_response_becomes_protocol_error(
) -> None:
    invalid_response = {
        **INCIDENT_RESPONSE,
        "severity": (
            "NOT-A-SEVERITY"
        ),
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=invalid_response,
        )

    gateway, client = build_gateway(
        handler
    )

    try:
        with pytest.raises(
            IncidentGatewayProtocolError,
            match=(
                "invalid incident list"
            ),
        ):
            gateway.list()

    finally:
        client.close()