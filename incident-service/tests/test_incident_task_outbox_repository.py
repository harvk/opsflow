from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

from sqlalchemy import (
    select,
)
from sqlalchemy.orm import (
    Session,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.models.incident_task_outbox import (
    IncidentTaskOutboxModel,
)
from app.repositories.sqlalchemy_incident_task_outbox_repository import (
    SqlAlchemyIncidentTaskOutboxRepository,
)

OUTBOX_ID = UUID(
    "11111111-1111-4111-8111-111111111111"
)

TASK_ID = UUID(
    "22222222-2222-4222-8222-222222222222"
)

INCIDENT_ID = UUID(
    "33333333-3333-4333-8333-333333333333"
)


def test_create_persists_pending_outbox_message(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskOutboxRepository(
            db_session
        )
    )

    now = datetime.now(
        UTC
    )

    message = (
        IncidentTaskOutboxMessage(
            id=OUTBOX_ID,
            task_id=TASK_ID,
            incident_id=(
                INCIDENT_ID
            ),
            schema_version="1.0",
            task_type=(
                "incident.processing.requested"
            ),
            idempotency_key=(
                "incident:"
                f"{INCIDENT_ID}:"
                "process:v1"
            ),
            correlation_id=(
                "correlation-11.5g.2"
            ),
            causation_id=None,
            payload={
                "incident_id": str(
                    INCIDENT_ID
                ),
            },
            metadata={
                "source": (
                    "incident-service"
                ),
                "operation": (
                    "incident.create"
                ),
            },
            created_at=now,
        )
    )

    repository.create(
        message
    )

    persisted = (
        db_session
        .scalar(
            select(
                IncidentTaskOutboxModel
            )
            .where(
                IncidentTaskOutboxModel.id
                == OUTBOX_ID
            )
        )
    )

    assert (
        persisted
        is not None
    )

    assert (
        persisted.task_id
        == TASK_ID
    )

    assert (
        persisted.incident_id
        == INCIDENT_ID
    )

    assert (
        persisted.task_type
        == (
            "incident.processing.requested"
        )
    )

    assert (
        persisted.publication_status
        == "PENDING"
    )

    assert (
        persisted.publish_attempts
        == 0
    )

    assert (
        persisted.published_at
        is None
    )

    assert (
        persisted.last_error
        is None
    )

    assert (
        persisted.payload
        == {
            "incident_id": str(
                INCIDENT_ID
            ),
        }
    )
