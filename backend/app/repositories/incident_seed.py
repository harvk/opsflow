from datetime import UTC, datetime
from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


def create_seed_incidents() -> list[Incident]:
    return [
        Incident(
            id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
            title="Payment webhook processing failures",
            service_id=UUID("44444444-4444-4444-8444-444444444444"),
            severity=IncidentSeverity.SEV_1,
            status=IncidentStatus.INVESTIGATING,
            summary=("Payment provider callbacks are experiencing elevated processing failures."),
            assignee="Jordan Lee",
            started_at=datetime(
                2026,
                9,
                4,
                16,
                5,
                tzinfo=UTC,
            ),
            resolved_at=None,
            created_at=datetime(
                2026,
                9,
                4,
                16,
                7,
                tzinfo=UTC,
            ),
            updated_at=datetime(
                2026,
                9,
                4,
                16,
                30,
                tzinfo=UTC,
            ),
        ),
        Incident(
            id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
            title="Inventory synchronization latency",
            service_id=UUID("22222222-2222-4222-8222-222222222222"),
            severity=IncidentSeverity.SEV_2,
            status=IncidentStatus.MONITORING,
            summary=(
                "Inventory updates are processing more slowly than the normal operating threshold."
            ),
            assignee="Morgan Reed",
            started_at=datetime(
                2026,
                9,
                4,
                12,
                20,
                tzinfo=UTC,
            ),
            resolved_at=None,
            created_at=datetime(
                2026,
                9,
                4,
                12,
                25,
                tzinfo=UTC,
            ),
            updated_at=datetime(
                2026,
                9,
                4,
                15,
                40,
                tzinfo=UTC,
            ),
        ),
        Incident(
            id=UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc"),
            title="Elevated Order API latency",
            service_id=UUID("11111111-1111-4111-8111-111111111111"),
            severity=IncidentSeverity.SEV_3,
            status=IncidentStatus.RESOLVED,
            summary=("Order API latency temporarily exceeded the normal operating threshold."),
            assignee="Alex Rivera",
            started_at=datetime(
                2026,
                9,
                3,
                18,
                10,
                tzinfo=UTC,
            ),
            resolved_at=datetime(
                2026,
                9,
                3,
                19,
                5,
                tzinfo=UTC,
            ),
            created_at=datetime(
                2026,
                9,
                3,
                18,
                12,
                tzinfo=UTC,
            ),
            updated_at=datetime(
                2026,
                9,
                3,
                19,
                5,
                tzinfo=UTC,
            ),
        ),
    ]
