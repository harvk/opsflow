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
from sqlalchemy.orm import (
    Session,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_completion import (
    EVENT_SCHEMA_VERSION,
    INCIDENT_TASK_COMPLETED_EVENT_TYPE,
    IncidentTaskCompletionOutboxMessage,
)
from app.repositories.sqlalchemy_incident_task_completion_outbox_repository import (
    IncidentTaskCompletionOutboxCollisionError,
    SqlAlchemyIncidentTaskCompletionOutboxRepository,
)


def build_message(
    *,
    task_id: UUID | None = None,
    incident_id: UUID | None = None,
    correlation_id: str = "correlation-4d",
) -> IncidentTaskCompletionOutboxMessage:
    now = datetime.now(
        UTC
    )

    return (
        IncidentTaskCompletionOutboxMessage(
            id=uuid4(),
            event_id=uuid4(),
            incident_id=(
                incident_id
                or uuid4()
            ),
            task_id=(
                task_id
                or uuid4()
            ),
            correlation_id=(
                correlation_id
            ),
            schema_version=(
                EVENT_SCHEMA_VERSION
            ),
            event_type=(
                INCIDENT_TASK_COMPLETED_EVENT_TYPE
            ),
            status=(
                IncidentStatus.INVESTIGATING
            ),
            acknowledged_at=now,
            occurred_at=now,
        )
    )


def test_create_round_trip(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    message = build_message()

    created = repository.create(
        message
    )

    assert created == message


def test_repeated_task_id_returns_existing_event(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    task_id = uuid4()
    incident_id = uuid4()

    first = build_message(
        task_id=task_id,
        incident_id=incident_id,
    )

    second = build_message(
        task_id=task_id,
        incident_id=incident_id,
    )

    first_result = repository.create(
        first
    )

    second_result = repository.create(
        second
    )

    assert first_result == first

    assert (
        second_result.event_id
        == first.event_id
    )

    assert (
        second_result.task_id
        == task_id
    )


def test_reused_task_id_for_different_incident_is_rejected(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    task_id = uuid4()

    repository.create(
        build_message(
            task_id=task_id,
            incident_id=uuid4(),
        )
    )

    with pytest.raises(
        IncidentTaskCompletionOutboxCollisionError,
        match=(
            "does not match"
        ),
    ):
        repository.create(
            build_message(
                task_id=task_id,
                incident_id=uuid4(),
            )
        )
