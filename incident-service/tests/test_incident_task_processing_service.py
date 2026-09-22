from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
    uuid4,
)

import pytest

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.services.exceptions import (
    IncidentNotFoundError,
)
from app.services.incident_task_processing_service import (
    IncidentTaskProcessingService,
)


class InMemoryIncidentRepository(
    IncidentRepository
):
    def __init__(
        self,
        incidents: list[
            Incident
        ],
    ) -> None:
        self.incidents = {
            incident.id: incident
            for incident in incidents
        }

        self.update_count = 0

    def list(
        self,
        *,
        search: str | None = None,
        service_id: UUID | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        return list(
            self.incidents.values()
        )[
            offset:
            offset + limit
        ]

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        return (
            self.incidents.get(
                incident_id
            )
        )

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        self.incidents[
            incident.id
        ] = incident

        return incident

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        self.update_count += 1

        self.incidents[
            incident.id
        ] = incident

        return incident

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        self.incidents.pop(
            incident_id,
            None,
        )

    def list_by_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        matches = [
            incident
            for incident
            in self.incidents.values()
            if (
                incident.service_id
                == service_id
            )
        ]

        return matches[
            offset:
            offset + limit
        ]


def build_incident(
    *,
    status: IncidentStatus,
    acknowledged_at: (
        datetime
        | None
    ) = None,
) -> Incident:
    now = datetime.now(
        UTC
    )

    return (
        Incident(
            id=uuid4(),
            title=(
                "11.5G processing test"
            ),
            service_id=(
                uuid4()
            ),
            severity=(
                IncidentSeverity.SEV_2
            ),
            status=status,
            summary=(
                "Incident used to verify asynchronous "
                "processing behavior."
            ),
            assignee=(
                "Platform Operations"
            ),
            started_at=now,
            resolved_at=(
                now
                if (
                    status
                    is IncidentStatus.RESOLVED
                )
                else None
            ),
            created_at=now,
            updated_at=now,
            source="manual",
            customer_impacting=False,
            acknowledged_at=(
                acknowledged_at
            ),
        )
    )


def test_open_incident_enters_investigation(
) -> None:
    incident = build_incident(
        status=(
            IncidentStatus.OPEN
        )
    )

    repository = (
        InMemoryIncidentRepository(
            [
                incident
            ]
        )
    )

    service = (
        IncidentTaskProcessingService(
            repository
        )
    )

    result = service.process(
        incident.id
    )

    persisted = (
        repository.get_by_id(
            incident.id
        )
    )

    assert persisted is not None

    assert (
        persisted.status
        is IncidentStatus.INVESTIGATING
    )

    assert (
        persisted.acknowledged_at
        is not None
    )

    assert result.changed is True

    assert (
        repository.update_count
        == 1
    )


def test_repeated_processing_is_idempotent(
) -> None:
    incident = build_incident(
        status=(
            IncidentStatus.INVESTIGATING
        ),
        acknowledged_at=(
            datetime.now(
                UTC
            )
        ),
    )

    repository = (
        InMemoryIncidentRepository(
            [
                incident
            ]
        )
    )

    service = (
        IncidentTaskProcessingService(
            repository
        )
    )

    result = service.process(
        incident.id
    )

    assert result.changed is False

    assert (
        repository.update_count
        == 0
    )


@pytest.mark.parametrize(
    "status",
    [
        IncidentStatus.MONITORING,
        IncidentStatus.RESOLVED,
    ],
)
def test_processing_does_not_regress_advanced_status(
    status: IncidentStatus,
) -> None:
    incident = build_incident(
        status=status
    )

    repository = (
        InMemoryIncidentRepository(
            [
                incident
            ]
        )
    )

    service = (
        IncidentTaskProcessingService(
            repository
        )
    )

    result = service.process(
        incident.id
    )

    persisted = (
        repository.get_by_id(
            incident.id
        )
    )

    assert persisted is not None

    assert (
        persisted.status
        is status
    )

    assert result.changed is False

    assert (
        repository.update_count
        == 0
    )


def test_missing_incident_is_permanent_error(
) -> None:
    repository = (
        InMemoryIncidentRepository(
            []
        )
    )

    service = (
        IncidentTaskProcessingService(
            repository
        )
    )

    incident_id = uuid4()

    with pytest.raises(
        IncidentNotFoundError,
        match=str(
            incident_id
        ),
    ):
        service.process(
            incident_id
        )
