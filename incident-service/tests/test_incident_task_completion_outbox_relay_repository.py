from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from uuid import (
    uuid4,
)

from sqlalchemy.orm import (
    Session,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.models.incident_task_completion_outbox import (
    IncidentTaskCompletionOutboxModel,
)
from app.repositories.sqlalchemy_incident_task_completion_outbox_repository import (
    SqlAlchemyIncidentTaskCompletionOutboxRepository,
)


def build_message(
) -> IncidentTaskCompletionOutboxMessage:
    now = datetime.now(
        UTC
    )

    return (
        IncidentTaskCompletionOutboxMessage(
            id=uuid4(),
            event_id=uuid4(),
            incident_id=uuid4(),
            task_id=uuid4(),
            correlation_id=str(
                uuid4()
            ),
            schema_version=(
                "1.0"
            ),
            event_type=(
                "incident.task.completed"
            ),
            status=(
                IncidentStatus
                .INVESTIGATING
            ),
            acknowledged_at=now,
            occurred_at=now,
        )
    )


def test_locks_pending_completion_event(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    message = build_message()

    repository.create(
        message
    )

    record = (
        repository
        .lock_next_publishable(
            retry_before=(
                datetime.now(
                    UTC
                )
            )
        )
    )

    assert record is not None

    assert (
        record.message.event_id
        == message.event_id
    )

    assert (
        record.message.task_id
        == message.task_id
    )

    assert (
        record.publish_attempts
        == 0
    )


def test_mark_published_updates_completion_delivery_state(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    message = build_message()

    repository.create(
        message
    )

    published_at = datetime.now(
        UTC
    )

    repository.mark_published(
        message.id,
        published_at=(
            published_at
        ),
    )

    model = db_session.get(
        IncidentTaskCompletionOutboxModel,
        message.id,
    )

    assert model is not None

    assert (
        model.publication_status
        == "PUBLISHED"
    )

    assert (
        model.publish_attempts
        == 1
    )

    assert (
        model.published_at
        == published_at
    )

    assert (
        model.last_error
        is None
    )


def test_failed_completion_event_obeys_retry_delay(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskCompletionOutboxRepository(
            db_session
        )
    )

    message = build_message()

    repository.create(
        message
    )

    failed_at = datetime.now(
        UTC
    )

    repository.mark_publish_failed(
        message.id,
        failed_at=(
            failed_at
        ),
        error=(
            "simulated completion publication failure"
        ),
    )

    immediate = (
        repository
        .lock_next_publishable(
            retry_before=(
                failed_at
                - timedelta(
                    seconds=1
                )
            )
        )
    )

    assert immediate is None

    eligible_again = (
        repository
        .lock_next_publishable(
            retry_before=(
                failed_at
                + timedelta(
                    seconds=1
                )
            )
        )
    )

    assert eligible_again is not None

    assert (
        eligible_again.message.id
        == message.id
    )

    assert (
        eligible_again.publish_attempts
        == 1
    )
