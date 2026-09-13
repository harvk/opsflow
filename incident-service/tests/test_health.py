from fastapi.testclient import (
    TestClient,
)

from app.core.config import (
    Settings,
)
from app.main import (
    create_app,
)


def test_health_endpoint_reports_incident_service_identity(
) -> None:
    test_settings = (
        Settings(
            app_name=(
                "OpsFlow Incident Service"
            ),
            app_env="test",
            api_v1_prefix="/api/v1",
        )
    )

    application = (
        create_app(
            test_settings
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