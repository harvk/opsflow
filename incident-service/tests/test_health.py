from uuid import UUID

from fastapi.testclient import (
    TestClient,
)

from app.core.config import (
    Settings,
)
from app.core.request_context import (
    REQUEST_ID_HEADER,
)
from app.main import (
    create_app,
)


def build_test_settings(
) -> Settings:
    return Settings(
        app_name=(
            "OpsFlow Incident Service"
        ),
        app_env="test",
        api_v1_prefix="/api/v1",
        database_url=(
            "postgresql+psycopg://"
            "test:test@localhost/test"
        ),
        core_backend_url=(
            "http://core-backend.test/api/v1"
        ),
    )


def test_health_endpoint_reports_incident_service_identity(
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
            "/api/v1/health"
        )

    assert response.status_code == 200

    assert response.json() == {
        "status": "ok",
        "service": (
            "OpsFlow Incident Service"
        ),
        "environment": "test",
    }

    generated_request_id = (
        response.headers[
            REQUEST_ID_HEADER
        ]
    )

    parsed_request_id = UUID(
        generated_request_id
    )

    assert (
        str(parsed_request_id)
        == generated_request_id
    )

    assert parsed_request_id.version == 4


def test_health_endpoint_preserves_safe_request_id(
) -> None:
    application = (
        create_app(
            build_test_settings()
        )
    )

    supplied_request_id = (
        "health-check:9.6.4"
    )

    with TestClient(
        application
    ) as client:
        response = client.get(
            "/api/v1/health",
            headers={
                REQUEST_ID_HEADER: (
                    supplied_request_id
                )
            },
        )

    assert response.status_code == 200

    assert (
        response.headers[
            REQUEST_ID_HEADER
        ]
        == supplied_request_id
    )
