from __future__ import annotations

from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_service_catalog_gateway,
)
from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app


class StubServiceCatalogGateway:
    def __init__(
        self,
        existing_service_ids: set[UUID],
    ) -> None:
        self._existing_service_ids = (
            existing_service_ids
        )

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        return (
            service_id
            in self._existing_service_ids
        )


@pytest.fixture
def api_client(
    db_session: Session,
) -> Generator[
    tuple[TestClient, UUID],
    None,
    None,
]:
    service_id = uuid4()

    application = create_app(
        Settings(
            app_name="OpsFlow Incident Service",
            app_env="test",
            api_v1_prefix="/api/v1",
            database_url=(
                "postgresql+psycopg://"
                "test:test@localhost/test"
            ),
        )
    )

    def override_db_session(
    ) -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[
        get_db_session
    ] = override_db_session

    application.dependency_overrides[
        get_service_catalog_gateway
    ] = lambda: StubServiceCatalogGateway(
        {service_id}
    )

    with TestClient(application) as client:
        yield client, service_id

    application.dependency_overrides.clear()


def test_incident_crud_contract(
    api_client: tuple[TestClient, UUID],
) -> None:
    client, service_id = api_client

    create_response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Elevated API latency",
            "serviceId": str(service_id),
            "severity": "SEV-2",
            "status": "Investigating",
            "summary": (
                "Requests exceed the latency target."
            ),
            "assignee": "Platform Operations",
            "source": "monitoring",
            "customerImpacting": True,
        },
    )

    assert create_response.status_code == 201

    created = create_response.json()
    incident_id = created["id"]

    assert created["serviceId"] == str(
        service_id
    )
    assert created["severity"] == "SEV-2"
    assert created["status"] == "Investigating"
    assert created["source"] == "monitoring"
    assert created["customerImpacting"] is True

    get_response = client.get(
        f"/api/v1/incidents/{incident_id}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == incident_id

    list_response = client.get(
        "/api/v1/incidents",
        params={
            "serviceId": str(service_id),
            "severity": "SEV-2",
            "status": "Investigating",
        },
    )

    assert list_response.status_code == 200
    assert [
        incident["id"]
        for incident in list_response.json()
    ] == [
        incident_id
    ]

    update_response = client.patch(
        f"/api/v1/incidents/{incident_id}",
        json={
            "status": "Resolved",
            "summary": "Latency returned to normal.",
            "customerImpacting": False,
        },
    )

    assert update_response.status_code == 200

    updated = update_response.json()

    assert updated["status"] == "Resolved"
    assert updated["summary"] == (
        "Latency returned to normal."
    )
    assert updated["customerImpacting"] is False
    assert updated["resolvedAt"] is not None

    delete_response = client.delete(
        f"/api/v1/incidents/{incident_id}"
    )

    assert delete_response.status_code == 204

    missing_response = client.get(
        f"/api/v1/incidents/{incident_id}"
    )

    assert missing_response.status_code == 404


def test_create_rejects_unknown_service_reference(
    api_client: tuple[TestClient, UUID],
) -> None:
    client, _service_id = api_client
    unknown_service_id = uuid4()

    response = client.post(
        "/api/v1/incidents",
        json={
            "title": "Unknown service incident",
            "serviceId": str(
                unknown_service_id
            ),
            "severity": "SEV-3",
            "summary": "Unknown service reference.",
            "assignee": "Platform Operations",
        },
    )

    assert response.status_code == 404
    assert str(unknown_service_id) in (
        response.json()["detail"]
    )


def test_get_returns_not_found_for_unknown_incident(
    api_client: tuple[TestClient, UUID],
) -> None:
    client, _service_id = api_client
    incident_id = uuid4()

    response = client.get(
        f"/api/v1/incidents/{incident_id}"
    )

    assert response.status_code == 404
    assert str(incident_id) in (
        response.json()["detail"]
    )


def test_create_fails_closed_when_catalog_is_unavailable(
    db_session: Session,
) -> None:
    application = create_app(
        Settings(
            app_name="OpsFlow Incident Service",
            app_env="test",
            api_v1_prefix="/api/v1",
            database_url=(
                "postgresql+psycopg://"
                "test:test@localhost/test"
            ),
        )
    )

    def override_db_session(
    ) -> Generator[Session, None, None]:
        yield db_session

    application.dependency_overrides[
        get_db_session
    ] = override_db_session

    with TestClient(application) as client:
        response = client.post(
            "/api/v1/incidents",
            json={
                "title": "Catalog unavailable",
                "serviceId": str(uuid4()),
                "severity": "SEV-2",
                "summary": (
                    "Catalog validation is unavailable."
                ),
                "assignee": "Platform Operations",
            },
        )

    application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"].startswith(
        "Service Catalog validation is unavailable."
    )