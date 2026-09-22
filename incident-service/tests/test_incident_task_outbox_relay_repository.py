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

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.models.incident_task_outbox import (
    IncidentTaskOutboxModel,
)
from app.repositories.sqlalchemy_incident_task_outbox_repository import (
    SqlAlchemyIncidentTaskOutboxRepository,
)


def build_message(
) -> IncidentTaskOutboxMessage:
    incident_id = uuid4()

    return (
        IncidentTaskOutboxMessage(
            id=uuid4(),
            task_id=uuid4(),
            incident_id=(
                incident_id
            ),
            schema_version="1.0",
            task_type=(
                "incident.processing.requested"
            ),
            idempotency_key=(
                "incident:"
                f"{incident_id}:"
                "process:v1"
            ),
            correlation_id=str(
                uuid4()
            ),
            causation_id=None,
            payload={
                "incident_id": str(
                    incident_id
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
            created_at=datetime.now(
                UTC
            ),
        )
    )


def test_locks_pending_record(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskOutboxRepository(
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
        record.message.task_id
        == message.task_id
    )

    assert (
        record.publish_attempts
        == 0
    )


def test_mark_published_updates_delivery_state(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskOutboxRepository(
            db_session
        )
    )

    message = build_message()

    repository.create(
        message
    )

    published_at = (
        datetime.now(
            UTC
        )
    )

    repository.mark_published(
        message.id,
        published_at=(
            published_at
        ),
    )

    model = db_session.get(
        IncidentTaskOutboxModel,
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


def test_failed_record_obeys_retry_delay(
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyIncidentTaskOutboxRepository(
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
            "simulated publication failure"
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
