from __future__ import annotations

from uuid import (
    UUID,
)

from fastapi.testclient import (
    TestClient,
)

from app.api.task_dependencies import (
    get_incident_notification_service,
)
from app.main import (
    app,
)
from app.messaging import (
    TaskEnvelope,
    TaskPublishError,
)
from app.services.incident_service import (
    IncidentNotFoundError,
)
from tests.constants import (
    PAYMENTS_INCIDENT_ID,
)

# =========================================================
# TEST VALUES
# =========================================================

REQUEST_ID = (
    "notification-api-test:11.5E.8"
)

TASK_ID = (
    "33333333-3333-4333-8333-333333333333"
)


# =========================================================
# TEST DOUBLES
# =========================================================


class SuccessfulNotificationService:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            tuple[
                UUID,
                str | None,
            ]
        ] = []

    def request_notification(
        self,
        *,
        incident_id: UUID,
        correlation_id: str | None,
    ) -> TaskEnvelope:
        self.calls.append(
            (
                incident_id,
                correlation_id,
            )
        )

        return TaskEnvelope(
            task_id=TASK_ID,
            task_type=(
                "incident.notification.requested"
            ),
            producer=(
                "opsflow-api"
            ),
            correlation_id=(
                correlation_id
                or "unexpected-fallback"
            ),
            idempotency_key=(
                f"incident:{incident_id}:"
                "notification-requested:v1"
            ),
            payload={
                "incident_id": str(
                    incident_id
                ),
            },
        )


class MissingIncidentNotificationService:
    def request_notification(
        self,
        *,
        incident_id: UUID,
        correlation_id: str | None,
    ) -> TaskEnvelope:
        del correlation_id

        raise IncidentNotFoundError(
            f"Incident {incident_id} "
            "was not found."
        )


class FailingNotificationService:
    def request_notification(
        self,
        *,
        incident_id: UUID,
        correlation_id: str | None,
    ) -> TaskEnvelope:
        del incident_id
        del correlation_id

        raise TaskPublishError(
            task_id=TASK_ID,
        )


# =========================================================
# SUCCESS CONTRACT
# =========================================================


def test_notification_endpoint_accepts_async_work(
    client: TestClient,
    auth_headers: dict[
        str,
        str,
    ],
) -> None:
    notification_service = (
        SuccessfulNotificationService()
    )

    app.dependency_overrides[
        get_incident_notification_service
    ] = (
        lambda: notification_service
    )

    try:
        response = client.post(
            (
                "/api/v1/incidents/"
                f"{PAYMENTS_INCIDENT_ID}"
                "/notification"
            ),
            headers={
                **auth_headers,
                "X-Request-ID": (
                    REQUEST_ID
                ),
            },
        )

    finally:
        app.dependency_overrides.pop(
            get_incident_notification_service,
            None,
        )

    assert (
        response.status_code
        == 202
    )

    assert (
        notification_service.calls
        == [
            (
                PAYMENTS_INCIDENT_ID,
                REQUEST_ID,
            ),
        ]
    )

    assert response.json() == {
        "status": "accepted",
        "taskId": TASK_ID,
        "taskType": (
            "incident.notification.requested"
        ),
        "correlationId": (
            REQUEST_ID
        ),
        "idempotencyKey": (
            f"incident:"
            f"{PAYMENTS_INCIDENT_ID}:"
            "notification-requested:v1"
        ),
    }

    assert (
        response.headers[
            "X-Request-ID"
        ]
        == REQUEST_ID
    )


# =========================================================
# INCIDENT ABSENCE CONTRACT
# =========================================================


def test_notification_endpoint_returns_404_for_missing_incident(
    client: TestClient,
    auth_headers: dict[
        str,
        str,
    ],
) -> None:
    app.dependency_overrides[
        get_incident_notification_service
    ] = (
        lambda: (
            MissingIncidentNotificationService()
        )
    )

    try:
        response = client.post(
            (
                "/api/v1/incidents/"
                f"{PAYMENTS_INCIDENT_ID}"
                "/notification"
            ),
            headers=(
                auth_headers
            ),
        )

    finally:
        app.dependency_overrides.pop(
            get_incident_notification_service,
            None,
        )

    assert (
        response.status_code
        == 404
    )


# =========================================================
# PUBLICATION FAILURE CONTRACT
# =========================================================


def test_notification_endpoint_returns_503_when_publication_fails(
    client: TestClient,
    auth_headers: dict[
        str,
        str,
    ],
) -> None:
    app.dependency_overrides[
        get_incident_notification_service
    ] = (
        lambda: (
            FailingNotificationService()
        )
    )

    try:
        response = client.post(
            (
                "/api/v1/incidents/"
                f"{PAYMENTS_INCIDENT_ID}"
                "/notification"
            ),
            headers=(
                auth_headers
            ),
        )

    finally:
        app.dependency_overrides.pop(
            get_incident_notification_service,
            None,
        )

    assert (
        response.status_code
        == 503
    )

    assert response.json() == {
        "detail": (
            "Asynchronous task publication "
            "is unavailable."
        )
    }
