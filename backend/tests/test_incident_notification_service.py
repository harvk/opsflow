from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

import pytest

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.messaging import (
    TaskEnvelope,
    TaskPublicationService,
)
from app.services.incident_notification_service import (
    INCIDENT_NOTIFICATION_OPERATION,
    INCIDENT_NOTIFICATION_TASK_TYPE,
    IncidentNotificationService,
)
from app.services.incident_service import (
    IncidentNotFoundError,
)

# =========================================================
# TEST VALUES
# =========================================================

INCIDENT_ID = UUID(
    "11111111-1111-4111-8111-111111111111"
)

SERVICE_ID = UUID(
    "22222222-2222-4222-8222-222222222222"
)

CORRELATION_ID = (
    "request:"
    "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
)

NOW = datetime(
    2026,
    9,
    19,
    3,
    0,
    0,
    tzinfo=UTC,
)


# =========================================================
# TEST DOUBLES
# =========================================================


class RecordingIncidentLookup:
    def __init__(
        self,
        incident: Incident,
    ) -> None:
        self._incident = (
            incident
        )

        self.requested_ids: list[
            UUID
        ] = []

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        self.requested_ids.append(
            incident_id
        )

        return (
            self._incident
        )


class MissingIncidentLookup:
    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        raise IncidentNotFoundError(
            f"Incident {incident_id} "
            "was not found."
        )


class RecordingTaskPublisher:
    def __init__(
        self,
    ) -> None:
        self.published: list[
            TaskEnvelope
        ] = []

    def publish(
        self,
        envelope: TaskEnvelope,
    ) -> None:
        self.published.append(
            envelope
        )


# =========================================================
# TEST HELPERS
# =========================================================


def build_incident(
) -> Incident:
    return Incident(
        id=INCIDENT_ID,
        service_id=SERVICE_ID,
        title=(
            "Checkout latency"
        ),
        severity=(
            IncidentSeverity.SEV_2
        ),
        status=(
            IncidentStatus.INVESTIGATING
        ),
        summary=(
            "Checkout requests are "
            "experiencing elevated latency."
        ),
        assignee=(
            "Platform Operations"
        ),
        source="monitoring",
        customer_impacting=True,
        acknowledged_at=None,
        started_at=NOW,
        resolved_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def build_service(
) -> tuple[
    IncidentNotificationService,
    RecordingIncidentLookup,
    RecordingTaskPublisher,
]:
    incident_lookup = (
        RecordingIncidentLookup(
            build_incident()
        )
    )

    publisher = (
        RecordingTaskPublisher()
    )

    publication_service = (
        TaskPublicationService(
            publisher=publisher,
            producer="opsflow-api",
        )
    )

    service = (
        IncidentNotificationService(
            incident_lookup=(
                incident_lookup
            ),
            task_publication_service=(
                publication_service
            ),
        )
    )

    return (
        service,
        incident_lookup,
        publisher,
    )


# =========================================================
# NOTIFICATION CONTRACT
# =========================================================


def test_request_notification_publishes_incident_task(
) -> None:
    (
        service,
        incident_lookup,
        publisher,
    ) = build_service()

    envelope = (
        service.request_notification(
            incident_id=(
                INCIDENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
        )
    )

    assert (
        incident_lookup.requested_ids
        == [
            INCIDENT_ID,
        ]
    )

    assert len(
        publisher.published
    ) == 1

    assert (
        publisher.published[0]
        is envelope
    )

    assert (
        envelope.task_type
        == INCIDENT_NOTIFICATION_TASK_TYPE
    )

    assert (
        envelope.correlation_id
        == CORRELATION_ID
    )

    assert (
        envelope.idempotency_key
        == (
            "incident:"
            "11111111-1111-4111-8111-111111111111:"
            f"{INCIDENT_NOTIFICATION_OPERATION}:"
            "v1"
        )
    )

    assert (
        envelope.payload
        == {
            "incident_id": str(
                INCIDENT_ID
            ),
            "service_id": str(
                SERVICE_ID
            ),
            "title": (
                "Checkout latency"
            ),
            "severity": "SEV-2",
            "status": (
                "Investigating"
            ),
            "summary": (
                "Checkout requests are "
                "experiencing elevated latency."
            ),
            "assignee": (
                "Platform Operations"
            ),
            "source": "monitoring",
            "customer_impacting": True,
        }
    )

    assert (
        envelope.metadata
        == {
            "workflow": (
                "incident-notification"
            )
        }
    )


def test_repeated_notification_request_reuses_business_key(
) -> None:
    (
        service,
        _incident_lookup,
        _publisher,
    ) = build_service()

    first = (
        service.request_notification(
            incident_id=(
                INCIDENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
        )
    )

    second = (
        service.request_notification(
            incident_id=(
                INCIDENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
        )
    )

    assert (
        first.task_id
        != second.task_id
    )

    assert (
        first.idempotency_key
        == second.idempotency_key
    )


def test_missing_incident_does_not_publish_task(
) -> None:
    publisher = (
        RecordingTaskPublisher()
    )

    service = (
        IncidentNotificationService(
            incident_lookup=(
                MissingIncidentLookup()
            ),
            task_publication_service=(
                TaskPublicationService(
                    publisher=publisher,
                    producer=(
                        "opsflow-api"
                    ),
                )
            ),
        )
    )

    with pytest.raises(
        IncidentNotFoundError,
        match=(
            "was not found"
        ),
    ):
        service.request_notification(
            incident_id=(
                INCIDENT_ID
            ),
            correlation_id=(
                CORRELATION_ID
            ),
        )

    assert (
        publisher.published
        == []
    )
