from fastapi import (
    FastAPI,
)
from fastapi.testclient import (
    TestClient,
)

from app.core.config import (
    Settings,
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
from app.middleware.request_correlation import (
    RequestCorrelationMiddleware,
)
from app.middleware.request_logging import (
    RequestLoggingMiddleware,
)


def build_test_settings(
) -> Settings:
    return Settings(
        app_name=(
            "OpsFlow Incident Service"
        ),
        app_env="test",
        api_v1_prefix="/api/v1",
        metrics_enabled=True,
        database_url=(
            "postgresql+psycopg://"
            "test:test@localhost/test"
        ),
        core_backend_url=(
            "http://core-backend.test/api/v1"
        ),
    )


def test_incident_metrics_use_normalized_route(
) -> None:
    metrics = (
        OperationalMetrics()
    )

    application = FastAPI()

    @application.get(
        "/incidents/{incident_id}"
    )
    def get_incident(
        incident_id: str,
    ) -> dict[
        str,
        str,
    ]:
        return {
            "incidentId": incident_id
        }

    application.add_middleware(
        MetricsMiddleware,
        metrics=metrics,
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/incidents/private-incident-123"
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
                    "/incidents/{incident_id}"
                ),
                "status_code": "200",
            },
        )
        == 1.0
    )

    assert (
        "private-incident-123"
        not in metrics.render()
        .decode(
            "utf-8"
        )
    )


def test_incident_service_exposes_private_metrics_endpoint(
) -> None:
    application = (
        create_app(
            build_test_settings()
        )
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


def test_incident_metrics_middleware_order(
) -> None:
    application = (
        create_app(
            build_test_settings()
        )
    )

    registered_middleware = (
        application
        .user_middleware
    )

    assert (
        registered_middleware[0].cls
        is RequestCorrelationMiddleware
    )

    assert (
        registered_middleware[1].cls
        is MetricsMiddleware
    )

    assert (
        registered_middleware[2].cls
        is RequestLoggingMiddleware
    )
