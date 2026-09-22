from __future__ import annotations

from collections.abc import (
    Callable,
    Generator,
)
from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
    uuid4,
)

import pytest
from sqlalchemy import (
    Connection,
    Engine,
    select,
)
from sqlalchemy.exc import (
    SQLAlchemyError,
)
from sqlalchemy.orm import (
    Session,
)

import app.workers.incident_task_reconciler as reconciler_module
from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.domain.incident_task_execution import (
    IncidentTaskExecution,
    IncidentTaskExecutionStatus,
)
from app.models.incident_task_completion_outbox import (
    IncidentTaskCompletionOutboxModel,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.workers.incident_task_reconciler import (
    RetryableIncidentTaskProcessingError,
    process_incident_with_postgres,
)


@pytest.fixture
def reconciler_connection(
    test_engine: Engine,
) -> Generator[
    Connection,
    None,
    None,
]:
    connection = (
        test_engine.connect()
    )

    transaction = (
        connection.begin()
    )

    try:
        yield connection

    finally:
        transaction.rollback()
        connection.close()


def build_session_factory(
    connection: Connection,
) -> Callable[
    [],
    Session,
]:
    def session_factory(
    ) -> Session:
        return (
            Session(
                bind=connection,
                autoflush=False,
                expire_on_commit=False,
                join_transaction_mode=(
                    "create_savepoint"
                ),
            )
        )

    return session_factory


def build_incident(
) -> Incident:
    now = datetime.now(
        UTC
    )

    return (
        Incident(
            id=uuid4(),
            service_id=uuid4(),
            title=(
                "11.5G.4D reconciliation transaction"
            ),
            severity=(
                IncidentSeverity.SEV_2
            ),
            status=(
                IncidentStatus.OPEN
            ),
            summary=(
                "Verifies Incident mutation and completion "
                "outbox persistence share one transaction."
            ),
            assignee=(
                "Platform Operations"
            ),
            source="manual",
            customer_impacting=False,
            acknowledged_at=None,
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
    )


def build_execution(
    incident_id: UUID,
) -> IncidentTaskExecution:
    return (
        IncidentTaskExecution(
            task_id=str(
                uuid4()
            ),
            incident_id=(
                incident_id
            ),
            task_type=(
                "incident.processing.requested"
            ),
            correlation_id=(
                "11.5G.4D:"
                f"{uuid4()}"
            ),
            created_at=(
                datetime.now(
                    UTC
                )
                .isoformat()
            ),
            status=(
                IncidentTaskExecutionStatus
                .INCIDENT_SERVICE_PROCESSING
            ),
            reconciliation_attempts=1,
            lease_expires_at=(
                9999999999
            ),
            reconciliation_token=(
                "transaction-test-token"
            ),
        )
    )


def seed_incident(
    session_factory: Callable[
        [],
        Session,
    ],
    incident: Incident,
) -> None:
    session = (
        session_factory()
    )

    try:
        repository = (
            SqlAlchemyIncidentRepository(
                session
            )
        )

        repository.create(
            incident
        )

        session.commit()

    finally:
        session.close()


def load_incident(
    session_factory: Callable[
        [],
        Session,
    ],
    incident_id: UUID,
) -> Incident:
    session = (
        session_factory()
    )

    try:
        repository = (
            SqlAlchemyIncidentRepository(
                session
            )
        )

        incident = (
            repository.get_by_id(
                incident_id
            )
        )

        assert incident is not None

        return incident

    finally:
        session.close()


def load_completion_rows(
    session_factory: Callable[
        [],
        Session,
    ],
    *,
    task_id: UUID,
) -> list[
    IncidentTaskCompletionOutboxModel
]:
    session = (
        session_factory()
    )

    try:
        statement = (
            select(
                IncidentTaskCompletionOutboxModel
            )
            .where(
                IncidentTaskCompletionOutboxModel
                .task_id
                == task_id
            )
            .order_by(
                IncidentTaskCompletionOutboxModel
                .created_at
                .asc()
            )
        )

        return list(
            session
            .scalars(
                statement
            )
            .all()
        )

    finally:
        session.close()


def test_reconciliation_commits_incident_and_completion_event_together(
    reconciler_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = (
        build_session_factory(
            reconciler_connection
        )
    )

    monkeypatch.setattr(
        reconciler_module,
        "SessionLocal",
        session_factory,
    )

    incident = (
        build_incident()
    )

    seed_incident(
        session_factory,
        incident,
    )

    execution = (
        build_execution(
            incident.id
        )
    )

    result = (
        process_incident_with_postgres(
            execution
        )
    )

    persisted_incident = (
        load_incident(
            session_factory,
            incident.id,
        )
    )

    rows = (
        load_completion_rows(
            session_factory,
            task_id=UUID(
                execution.task_id
            ),
        )
    )

    assert (
        result.incident_id
        == incident.id
    )

    assert (
        result.status
        is IncidentStatus.INVESTIGATING
    )

    assert result.changed is True

    assert (
        result.acknowledged_at
        is not None
    )

    assert (
        persisted_incident.status
        is IncidentStatus.INVESTIGATING
    )

    assert (
        persisted_incident
        .acknowledged_at
        is not None
    )

    assert len(
        rows
    ) == 1

    completion = (
        rows[0]
    )

    assert (
        completion.incident_id
        == incident.id
    )

    assert (
        completion.task_id
        == UUID(
            execution.task_id
        )
    )

    assert (
        completion.correlation_id
        == execution.correlation_id
    )

    assert (
        completion.schema_version
        == "1.0"
    )

    assert (
        completion.event_type
        == "incident.task.completed"
    )

    assert (
        completion.status
        == "Investigating"
    )

    assert (
        completion.acknowledged_at
        == (
            persisted_incident
            .acknowledged_at
        )
    )

    assert (
        completion.publication_status
        == "PENDING"
    )

    assert (
        completion.publish_attempts
        == 0
    )


def test_reconciliation_retry_reuses_same_completion_event(
    reconciler_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = (
        build_session_factory(
            reconciler_connection
        )
    )

    monkeypatch.setattr(
        reconciler_module,
        "SessionLocal",
        session_factory,
    )

    incident = (
        build_incident()
    )

    seed_incident(
        session_factory,
        incident,
    )

    execution = (
        build_execution(
            incident.id
        )
    )

    first_result = (
        process_incident_with_postgres(
            execution
        )
    )

    first_rows = (
        load_completion_rows(
            session_factory,
            task_id=UUID(
                execution.task_id
            ),
        )
    )

    assert len(
        first_rows
    ) == 1

    first_event_id = (
        first_rows[0]
        .event_id
    )

    first_occurred_at = (
        first_rows[0]
        .occurred_at
    )

    second_result = (
        process_incident_with_postgres(
            execution
        )
    )

    second_rows = (
        load_completion_rows(
            session_factory,
            task_id=UUID(
                execution.task_id
            ),
        )
    )

    assert (
        first_result.changed
        is True
    )

    assert (
        second_result.changed
        is False
    )

    assert len(
        second_rows
    ) == 1

    assert (
        second_rows[0]
        .event_id
        == first_event_id
    )

    assert (
        second_rows[0]
        .occurred_at
        == first_occurred_at
    )


def test_completion_outbox_failure_rolls_back_incident_change(
    reconciler_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = (
        build_session_factory(
            reconciler_connection
        )
    )

    monkeypatch.setattr(
        reconciler_module,
        "SessionLocal",
        session_factory,
    )

    incident = (
        build_incident()
    )

    seed_incident(
        session_factory,
        incident,
    )

    execution = (
        build_execution(
            incident.id
        )
    )

    def fail_completion_create(
        _self,
        _message,
    ):
        raise SQLAlchemyError(
            "simulated completion outbox failure"
        )

    monkeypatch.setattr(
        (
            reconciler_module
            .SqlAlchemyIncidentTaskCompletionOutboxRepository
        ),
        "create",
        fail_completion_create,
    )

    with pytest.raises(
        RetryableIncidentTaskProcessingError,
        match=(
            "completion-event persistence failed"
        ),
    ):
        process_incident_with_postgres(
            execution
        )

    persisted_incident = (
        load_incident(
            session_factory,
            incident.id,
        )
    )

    rows = (
        load_completion_rows(
            session_factory,
            task_id=UUID(
                execution.task_id
            ),
        )
    )

    assert (
        persisted_incident.status
        is IncidentStatus.OPEN
    )

    assert (
        persisted_incident
        .acknowledged_at
        is None
    )

    assert rows == []
