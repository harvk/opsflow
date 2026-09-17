from __future__ import annotations

import json
from collections.abc import (
    Callable,
    Collection,
)
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)
from app.core.metrics import (
    OperationalMetrics,
)
from app.core.request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    reset_request_id,
)
from app.core.service_identity import (
    ServiceScope,
)
from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.incident_gateway import (
    IncidentGatewayCircuitOpenError,
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

INCIDENT_SERVICE_AUDIENCE = (
    "opsflow-incident-service"
)

SERVICE_TOKEN = "signed-service-jwt"

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


class FakeClock:
    def __init__(
        self,
    ) -> None:
        self.current_seconds = 0.0

    def __call__(
        self,
    ) -> float:
        return (
            self.current_seconds
        )

    def advance(
        self,
        seconds: float,
    ) -> None:
        self.current_seconds += (
            seconds
        )


class RecordingServiceTokenProvider:
    def __init__(
        self,
        *,
        token: str = SERVICE_TOKEN,
    ) -> None:
        self.token = token
        self.calls: list[
            tuple[
                str,
                frozenset[ServiceScope],
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
        self.calls.append(
            (
                audience,
                frozenset(scopes),
            )
        )

        return self.token


def no_sleep(
    _delay_seconds: float,
) -> None:
    """
    Test sleeper that deliberately performs no wall-clock
    delay.
    """

    return


def build_gateway(
    handler: Callable[
        [httpx.Request],
        httpx.Response,
    ],
    *,
    read_max_attempts: int = 1,
    read_backoff_seconds: float = 0.0,
    sleeper: Callable[
        [float],
        None,
    ] = no_sleep,
    circuit_breaker: (
        CircuitBreaker
        | None
    ) = None,
    metrics: (
        OperationalMetrics
        | None
    ) = None,
    service_token_provider: (
        RecordingServiceTokenProvider
        | None
    ) = None,
) -> tuple[
    HttpIncidentGateway,
    httpx.Client,
]:
    client = httpx.Client(
        transport=httpx.MockTransport(
            handler
        )
    )

    provider = (
        service_token_provider
        or RecordingServiceTokenProvider()
    )

    gateway = HttpIncidentGateway(
        client=client,
        incident_service_url=(
            INCIDENT_SERVICE_URL
        ),
        service_token_provider=provider,
        incident_service_audience=(
            INCIDENT_SERVICE_AUDIENCE
        ),
        read_max_attempts=(
            read_max_attempts
        ),
        read_backoff_seconds=(
            read_backoff_seconds
        ),
        sleeper=sleeper,
        circuit_breaker=(
            circuit_breaker
        ),
        metrics=metrics
    )

    return gateway, client


def assert_service_authentication(
    request: httpx.Request,
) -> None:
    assert (
        request.headers[
            "Authorization"
        ]
        == f"Bearer {SERVICE_TOKEN}"
    )

    assert (
        "X-OpsFlow-Internal-Token"
        not in request.headers
    )


def test_read_uses_only_incidents_read_scope(
) -> None:
    provider = RecordingServiceTokenProvider()

    gateway, client = build_gateway(
        lambda _request: httpx.Response(
            200,
            json=[],
        ),
        service_token_provider=provider,
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
                    ServiceScope.INCIDENTS_READ
                }
            ),
        )
    ]


def test_mutation_uses_only_incidents_write_scope(
) -> None:
    provider = RecordingServiceTokenProvider()

    gateway, client = build_gateway(
        lambda _request: httpx.Response(
            201,
            json=INCIDENT_RESPONSE,
        ),
        service_token_provider=provider,
    )

    payload = IncidentCreate(
        title="Checkout latency",
        service_id=SERVICE_ID,
        severity=IncidentSeverity.SEV_2,
        summary="Checkout latency is elevated.",
        assignee="Platform Team",
        source="monitoring",
    )

    try:
        gateway.create(payload)

    finally:
        client.close()

    assert provider.calls == [
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope.INCIDENTS_WRITE
                }
            ),
        )
    ]

def test_gateway_propagates_only_the_current_request_id(
) -> None:
    observed_request_ids: list[
        str | None
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        observed_request_ids.append(
            request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        assert_service_authentication(
            request
        )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        handler
    )

    request_id = (
        "backend-request-9.6.4"
    )

    try:
        context_token = bind_request_id(
            request_id
        )

        try:
            assert gateway.list() == []

        finally:
            reset_request_id(
                context_token
            )

        assert gateway.list() == []

    finally:
        client.close()

    assert observed_request_ids == [
        request_id,
        None,
    ]


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

        assert_service_authentication(
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

        assert_service_authentication(
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

        assert_service_authentication(
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

        assert_service_authentication(
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


def test_safe_read_retries_timeout_and_preserves_request_id(
) -> None:
    attempt_count = 0

    provider = RecordingServiceTokenProvider()

    observed_request_ids: list[
        str | None
    ] = []

    observed_delays: list[
        float
    ] = []

    request_id = (
        "safe-read-retry:9.6.6"
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal attempt_count

        attempt_count += 1

        observed_request_ids.append(
            request.headers.get(
                REQUEST_ID_HEADER
            )
        )

        if attempt_count == 1:
            raise httpx.ReadTimeout(
                "first attempt timed out",
                request=request,
            )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        handler,
        read_max_attempts=2,
        read_backoff_seconds=0.25,
        sleeper=(
            observed_delays.append
        ),
        service_token_provider=provider,
    )

    context_token = bind_request_id(
        request_id
    )

    try:
        try:
            assert gateway.list() == []

        finally:
            reset_request_id(
                context_token
            )

    finally:
        client.close()

    assert attempt_count == 2

    assert observed_request_ids == [
        request_id,
        request_id,
    ]

    assert observed_delays == [
        0.25
    ]

    assert provider.calls == [
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope.INCIDENTS_READ
                }
            ),
        ),
        (
            INCIDENT_SERVICE_AUDIENCE,
            frozenset(
                {
                    ServiceScope.INCIDENTS_READ
                }
            ),
        ),
    ]


def test_safe_read_metrics_distinguish_retry_attempts(
) -> None:
    attempt_count = 0

    metrics = (
        OperationalMetrics()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal attempt_count

        attempt_count += 1

        if attempt_count == 1:
            raise httpx.ReadTimeout(
                "first attempt timed out",
                request=request,
            )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        handler,
        read_max_attempts=2,
        metrics=metrics,
    )

    try:
        assert gateway.list() == []

    finally:
        client.close()

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_dependency_operations_total"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "method": "GET",
                "outcome": "2xx",
            },
        )
        == 1.0
    )

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_dependency_attempts_total"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "method": "GET",
                "outcome": "timeout",
            },
        )
        == 1.0
    )

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_dependency_attempts_total"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "method": "GET",
                "outcome": "2xx",
            },
        )
        == 1.0
    )

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_dependency_retries_total"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "method": "GET",
                "reason": "timeout",
            },
        )
        == 1.0
    )


def test_safe_read_retries_transient_503_response(
) -> None:
    attempt_count = 0

    observed_delays: list[
        float
    ] = []

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        nonlocal attempt_count

        attempt_count += 1

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
        handler,
        read_max_attempts=2,
        read_backoff_seconds=0.1,
        sleeper=(
            observed_delays.append
        ),
    )

    try:
        assert gateway.list() == []

    finally:
        client.close()

    assert attempt_count == 2

    assert observed_delays == [
        0.1
    ]


def test_safe_read_stops_at_configured_attempt_limit(
) -> None:
    attempt_count = 0

    observed_delays: list[
        float
    ] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal attempt_count

        attempt_count += 1

        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler,
        read_max_attempts=3,
        read_backoff_seconds=0.25,
        sleeper=(
            observed_delays.append
        ),
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

    assert attempt_count == 3

    assert observed_delays == [
        0.25,
        0.5,
    ]


def test_mutations_are_never_automatically_retried(
) -> None:
    observed_methods: list[
        str
    ] = []

    observed_delays: list[
        float
    ] = []

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

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        observed_methods.append(
            request.method
        )

        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler,
        read_max_attempts=3,
        read_backoff_seconds=0.25,
        sleeper=(
            observed_delays.append
        ),
    )

    operations: list[
        Callable[
            [HttpIncidentGateway],
            object,
        ]
    ] = [
        lambda active_gateway: (
            active_gateway.create(
                create_payload
            )
        ),
        lambda active_gateway: (
            active_gateway.update(
                INCIDENT_ID,
                update_payload,
            )
        ),
        lambda active_gateway: (
            active_gateway.delete(
                INCIDENT_ID
            )
        ),
    ]

    try:
        for operation in operations:
            with pytest.raises(
                IncidentGatewayUnavailableError
            ):
                operation(
                    gateway
                )

    finally:
        client.close()

    assert observed_methods == [
        "POST",
        "PATCH",
        "DELETE",
    ]

    assert observed_delays == []


def test_gateway_opens_circuit_after_failed_operations(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=10.0,
        clock=clock,
    )

    transport_attempts = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal transport_attempts

        transport_attempts += 1

        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler,
        circuit_breaker=circuit,
    )

    try:
        for _operation_number in range(
            2
        ):
            with pytest.raises(
                IncidentGatewayUnavailableError
            ):
                gateway.list()

        assert (
            circuit.state
            is CircuitState.OPEN
        )

        with pytest.raises(
            IncidentGatewayCircuitOpenError
        ) as captured_error:
            gateway.list()

    finally:
        client.close()

    assert transport_attempts == 2

    assert (
        captured_error
        .value
        .retry_after_seconds
        == 10
    )


def test_gateway_metrics_report_open_circuit(
) -> None:
    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=10.0,
    )

    metrics = (
        OperationalMetrics()
    )

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler,
        circuit_breaker=circuit,
        metrics=metrics,
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError
        ):
            gateway.list()

        with pytest.raises(
            IncidentGatewayCircuitOpenError
        ):
            gateway.list()

    finally:
        client.close()

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_circuit_breaker_state"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "state": "open",
            },
        )
        == 1.0
    )

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_dependency_operations_total"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "method": "GET",
                "outcome": (
                    "circuit_open"
                ),
            },
        )
        == 1.0
    )


def test_successful_half_open_probe_closes_circuit(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=5.0,
        clock=clock,
    )

    transport_attempts = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal transport_attempts

        transport_attempts += 1

        if transport_attempts == 1:
            raise httpx.ConnectError(
                "connection refused",
                request=request,
            )

        return httpx.Response(
            200,
            json=[],
        )

    gateway, client = build_gateway(
        handler,
        circuit_breaker=circuit,
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError
        ):
            gateway.list()

        assert (
            circuit.state
            is CircuitState.OPEN
        )

        clock.advance(
            5.0
        )

        assert gateway.list() == []

    finally:
        client.close()

    assert transport_attempts == 2

    assert (
        circuit.state
        is CircuitState.CLOSED
    )


def test_failed_half_open_probe_uses_one_transport_attempt(
) -> None:
    clock = FakeClock()

    circuit = CircuitBreaker(
        failure_threshold=1,
        recovery_seconds=5.0,
        clock=clock,
    )

    initial_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        initial_permit
    )

    clock.advance(
        5.0
    )

    transport_attempts = 0

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal transport_attempts

        transport_attempts += 1

        raise httpx.ConnectError(
            "connection refused",
            request=request,
        )

    gateway, client = build_gateway(
        handler,
        read_max_attempts=3,
        read_backoff_seconds=0.25,
        circuit_breaker=circuit,
    )

    try:
        with pytest.raises(
            IncidentGatewayUnavailableError
        ):
            gateway.list()

    finally:
        client.close()

    assert transport_attempts == 1

    assert (
        circuit.state
        is CircuitState.OPEN
    )


def test_client_response_resets_circuit_failure_count(
) -> None:
    circuit = CircuitBreaker(
        failure_threshold=3,
        recovery_seconds=10.0,
    )

    failed_permit = (
        circuit.acquire_permission()
    )

    circuit.record_failure(
        failed_permit
    )

    assert (
        circuit.consecutive_failures
        == 1
    )

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        # A 404 proves that the remote service responded.
        return httpx.Response(
            404,
            json={
                "detail": (
                    "Incident was not found."
                )
            },
        )

    gateway, client = build_gateway(
        handler,
        circuit_breaker=circuit,
    )

    try:
        with pytest.raises(
            IncidentNotFoundError
        ):
            gateway.get_by_id(
                INCIDENT_ID
            )

    finally:
        client.close()

    assert (
        circuit.state
        is CircuitState.CLOSED
    )

    assert (
        circuit.consecutive_failures
        == 0
    )


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

    assert SERVICE_TOKEN not in str(
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