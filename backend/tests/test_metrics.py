import pytest
from fastapi import (
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

from app.core.metrics import (
    OperationalMetrics,
)
from app.main import (
    create_app,
)
from app.middleware.metrics import (
    MetricsMiddleware,
)


def test_metrics_records_normalized_route_instead_of_identifier(
) -> None:
    metrics = (
        OperationalMetrics()
    )

    application = FastAPI()

    @application.get(
        "/items/{item_id}"
    )
    def get_item(
        item_id: str,
    ) -> dict[
        str,
        str,
    ]:
        return {
            "itemId": item_id
        }

    application.add_middleware(
        MetricsMiddleware,
        metrics=metrics,
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/items/private-resource-123"
        )

    assert response.status_code == 200

    assert (
        metrics.registry
        .get_sample_value(
            (
                "opsflow_http_requests_total"
            ),
            {
                "method": "GET",
                "route": (
                    "/items/{item_id}"
                ),
                "status_code": "200",
            },
        )
        == 1.0
    )

    rendered_metrics = (
        metrics.render()
        .decode(
            "utf-8"
        )
    )

    assert (
        "private-resource-123"
        not in rendered_metrics
    )


def test_dependency_metrics_distinguish_operations_attempts_and_retries(
) -> None:
    metrics = (
        OperationalMetrics()
    )

    metrics.record_dependency_attempt(
        dependency=(
            "incident_service"
        ),
        method="GET",
        outcome="timeout",
    )

    metrics.record_dependency_retry(
        dependency=(
            "incident_service"
        ),
        method="GET",
        reason="timeout",
    )

    metrics.record_dependency_attempt(
        dependency=(
            "incident_service"
        ),
        method="GET",
        outcome="2xx",
    )

    metrics.observe_dependency_operation(
        dependency=(
            "incident_service"
        ),
        method="GET",
        outcome="2xx",
        duration_seconds=0.25,
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


def test_circuit_state_is_one_hot(
) -> None:
    metrics = (
        OperationalMetrics()
    )

    metrics.set_circuit_state(
        dependency=(
            "incident_service"
        ),
        state="open",
    )

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
                "state": "closed",
            },
        )
        == 0.0
    )

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
                "opsflow_circuit_breaker_state"
            ),
            {
                "dependency": (
                    "incident_service"
                ),
                "state": "half_open",
            },
        )
        == 0.0
    )


def test_service_security_metrics_use_bounded_labels(
) -> None:
    metrics = OperationalMetrics()

    metrics.record_service_authentication(
        outcome="success",
        reason="authenticated",
    )
    metrics.record_service_authentication(
        outcome="failure",
        reason="invalid_signature",
    )
    metrics.record_service_authorization(
        outcome="denied",
        scope="services:read",
    )

    assert metrics.registry.get_sample_value(
        "opsflow_service_authentication_attempts_total",
        {
            "outcome": "failure",
            "reason": "invalid_signature",
        },
    ) == 1.0

    assert metrics.registry.get_sample_value(
        "opsflow_service_authorization_decisions_total",
        {
            "outcome": "denied",
            "scope": "services:read",
        },
    ) == 1.0


def test_service_security_metrics_reject_unbounded_labels(
) -> None:
    metrics = OperationalMetrics()

    with pytest.raises(
        ValueError,
        match="authentication reason",
    ):
        metrics.record_service_authentication(
            outcome="failure",
            reason="attacker-controlled-value",
        )

    with pytest.raises(
        ValueError,
        match="authorization scope",
    ):
        metrics.record_service_authorization(
            outcome="denied",
            scope="services:delete",
        )

def test_backend_exposes_metrics_outside_openapi(
) -> None:
    application = (
        create_app()
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/metrics"
        )

    assert response.status_code == 200

    assert response.headers[
        "content-type"
    ].startswith(
        "text/plain"
    )

    assert (
        "opsflow_http_requests_total"
        in response.text
    )

    assert (
        "/metrics"
        not in application.openapi()[
            "paths"
        ]
    )
