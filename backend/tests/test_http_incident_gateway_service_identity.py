from __future__ import annotations

from collections.abc import (
    Collection,
)
from inspect import (
    Parameter,
    signature,
)
from uuid import (
    UUID,
)

import httpx
import pytest

from app.core.service_identity import (
    ServiceScope,
    ServiceTokenCreationError,
)
from app.domain.incident import (
    IncidentSeverity,
)
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.incident_gateway import (
    IncidentGatewayUnavailableError,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
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

INCIDENT_SERVICE_AUDIENCE = (
    "opsflow-incident-service"
)

READ_TOKEN = "read-service-token"
WRITE_TOKEN = "write-service-token"

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


class RecordingServiceTokenProvider:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            tuple[
                str,
                frozenset[
                    ServiceScope
                ],
            ]
        ] = []

    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[
            ServiceScope
        ],
    ) -> str:
        normalized_scopes = (
            frozenset(
                scopes
            )
        )

        self.calls.append(
            (
                audience,
                normalized_scopes,
            )
        )

        if normalized_scopes == {
            ServiceScope.INCIDENTS_READ
        }:
            return READ_TOKEN

        if normalized_scopes == {
            ServiceScope.INCIDENTS_WRITE
        }:
            return WRITE_TOKEN

        raise AssertionError(
            "Unexpected service scope."
        )


class FailingServiceTokenProvider:
    def create_token(
        self,
        *,
        audience: str,
        scopes: Collection[
            ServiceScope
        ],
    ) -> str:
        del audience
        del scopes

        raise ServiceTokenCreationError(
            "sensitive-provider-detail"
        )


def build_gateway(
    handler: httpx.MockTransport,
    provider: (
        RecordingServiceTokenProvider
        | FailingServiceTokenProvider
    ),
    *,
    read_max_attempts: int = 1,
) -> tuple[
    HttpIncidentGateway,
    httpx.Client,
]:
    client = httpx.Client(
        transport=handler
    )

    gateway = HttpIncidentGateway(
        client=client,
        incident_service_url=(
            INCIDENT_SERVICE_URL
        ),
        service_token_provider=(
            provider
        ),
        incident_service_audience=(
            INCIDENT_SERVICE_AUDIENCE
        ),
        read_max_attempts=(
            read_max_attempts
        ),
    )

    return gateway, client


def test_read_uses_bearer_token_with_read_scope(
) -> None:
    provider = (
        RecordingServiceTokenProvider()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.headers[
            "Authorization"
        ] == f"Bearer {READ_TOKEN}"

        assert (
            "X-OpsFlow-Internal-Token"
            not in request.headers
        )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        httpx.MockTransport(
            handler
        ),
        provider,
    )

    try:
        assert gateway.list() == []

    finally:
        client.close()

    assert provider.calls == [
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope
                    .INCIDENTS_READ
                }
            ),
        )
    ]


def test_mutations_use_bearer_token_with_write_scope(
) -> None:
    provider = (
        RecordingServiceTokenProvider()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.headers[
            "Authorization"
        ] == f"Bearer {WRITE_TOKEN}"

        assert (
            "X-OpsFlow-Internal-Token"
            not in request.headers
        )

        if request.method == "POST":
            return httpx.Response(
                201,
                json=INCIDENT_RESPONSE,
            )

        if request.method == "PATCH":
            return httpx.Response(
                200,
                json=INCIDENT_RESPONSE,
            )

        if request.method == "DELETE":
            return httpx.Response(
                204
            )

        raise AssertionError(
            "Unexpected HTTP method."
        )

    gateway, client = build_gateway(
        httpx.MockTransport(
            handler
        ),
        provider,
    )

    create_payload = IncidentCreate(
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

    update_payload = IncidentUpdate(
        summary=(
            "Checkout latency remains elevated."
        )
    )

    try:
        gateway.create(
            create_payload
        )
        gateway.update(
            INCIDENT_ID,
            update_payload,
        )
        gateway.delete(
            INCIDENT_ID
        )

    finally:
        client.close()

    assert provider.calls == [
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope
                    .INCIDENTS_WRITE
                }
            ),
        ),
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope
                    .INCIDENTS_WRITE
                }
            ),
        ),
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope
                    .INCIDENTS_WRITE
                }
            ),
        ),
    ]


def test_read_retry_creates_token_for_each_transport_attempt(
) -> None:
    provider = (
        RecordingServiceTokenProvider()
    )

    attempt_count = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal attempt_count

        attempt_count += 1

        assert request.headers[
            "Authorization"
        ] == f"Bearer {READ_TOKEN}"

        if attempt_count == 1:
            return httpx.Response(
                503,
                json={
                    "detail": (
                        "Temporarily unavailable."
                    )
                },
            )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        httpx.MockTransport(
            handler
        ),
        provider,
        read_max_attempts=2,
    )

    try:
        assert gateway.list() == []

    finally:
        client.close()

    assert attempt_count == 2
    assert len(
        provider.calls
    ) == 2


def test_token_creation_failure_is_fail_closed(
) -> None:
    transport_attempted = False

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        nonlocal transport_attempted

        transport_attempted = True

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        httpx.MockTransport(
            handler
        ),
        FailingServiceTokenProvider(),
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError,
            match=(
                "authentication is unavailable"
            ),
        ) as captured_error:
            gateway.list()

    finally:
        client.close()

    assert not transport_attempted
    assert (
        "sensitive-provider-detail"
        not in str(
            captured_error.value
        )
    )
    assert (
        captured_error
        .value
        .__cause__
        is None
    )


def test_service_identity_configuration_is_required(
) -> None:
    parameters = signature(
        HttpIncidentGateway
    ).parameters

    assert (
        parameters[
            "service_token_provider"
        ].default
        is Parameter.empty
    )

    assert (
        parameters[
            "incident_service_audience"
        ].default
        is Parameter.empty
    )


def test_blank_service_identity_audience_is_rejected(
) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json=[],
            )
        )
    )

    try:
        with pytest.raises(
            ValueError,
            match=(
                "incident_service_audience "
                "must not be empty"
            ),
        ):
            HttpIncidentGateway(
                client=client,
                incident_service_url=(
                    INCIDENT_SERVICE_URL
                ),
                service_token_provider=(
                    RecordingServiceTokenProvider()
                ),
                incident_service_audience=(
                    "   "
                ),
            )

    finally:
        client.close()
