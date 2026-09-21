from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from uuid import (
    uuid4,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_execution import (
    IncidentTaskExecution,
    IncidentTaskExecutionStatus,
)
from app.services.exceptions import (
    IncidentNotFoundError,
)
from app.services.incident_task_processing_service import (
    IncidentProcessingResult,
)
from app.workers.incident_task_reconciler import (
    IncidentTaskReconciler,
    RetryableIncidentTaskProcessingError,
)


class RecordingExecutionRepository:
    def __init__(
        self,
        executions: list[
            IncidentTaskExecution
        ],
    ) -> None:
        self.executions = (
            executions
        )

        self.succeeded: list[
            str
        ] = []

        self.retryable: list[
            str
        ] = []

        self.failed: list[
            str
        ] = []

    def list_reconcilable(
        self,
        *,
        limit: int,
    ) -> list[
        IncidentTaskExecution
    ]:
        return (
            self.executions[
                :limit
            ]
        )

    def claim(
        self,
        execution: IncidentTaskExecution,
        *,
        lease_seconds: int,
    ) -> (
        IncidentTaskExecution
        | None
    ):
        assert (
            lease_seconds
            == 60
        )

        return (
            IncidentTaskExecution(
                task_id=(
                    execution.task_id
                ),
                incident_id=(
                    execution.incident_id
                ),
                task_type=(
                    execution.task_type
                ),
                correlation_id=(
                    execution
                    .correlation_id
                ),
                created_at=(
                    execution.created_at
                ),
                status=(
                    IncidentTaskExecutionStatus
                    .INCIDENT_SERVICE_PROCESSING
                ),
                reconciliation_attempts=(
                    execution
                    .reconciliation_attempts
                    + 1
                ),
                lease_expires_at=(
                    9999999999
                ),
                reconciliation_token=(
                    "test-token"
                ),
            )
        )

    def mark_succeeded(
        self,
        execution: IncidentTaskExecution,
        *,
        result: dict[
            str,
            object,
        ],
    ) -> None:
        self.succeeded.append(
            execution.task_id
        )

    def mark_retryable_failure(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        self.retryable.append(
            execution.task_id
        )

    def mark_failed(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        self.failed.append(
            execution.task_id
        )


def build_execution(
) -> IncidentTaskExecution:
    return (
        IncidentTaskExecution(
            task_id=str(
                uuid4()
            ),
            incident_id=(
                uuid4()
            ),
            task_type=(
                "incident.processing.requested"
            ),
            correlation_id=str(
                uuid4()
            ),
            created_at=(
                datetime.now(
                    UTC
                )
                .isoformat()
            ),
            status=(
                IncidentTaskExecutionStatus
                .READY_FOR_INCIDENT_SERVICE
            ),
            reconciliation_attempts=0,
        )
    )


def test_successful_reconciliation_marks_succeeded(
) -> None:
    execution = (
        build_execution()
    )

    repository = (
        RecordingExecutionRepository(
            [
                execution
            ]
        )
    )

    def processor(
        incident_id,
    ) -> IncidentProcessingResult:
        return (
            IncidentProcessingResult(
                incident_id=(
                    incident_id
                ),
                status=(
                    IncidentStatus
                    .INVESTIGATING
                ),
                changed=True,
                acknowledged_at=(
                    datetime.now(
                        UTC
                    )
                ),
            )
        )

    reconciler = (
        IncidentTaskReconciler(
            execution_repository=(
                repository
            ),
            processor=processor,
            batch_size=10,
            lease_seconds=60,
        )
    )

    summary = (
        reconciler
        .reconcile_once()
    )

    assert summary.succeeded == 1

    assert (
        repository.succeeded
        == [
            execution.task_id
        ]
    )


def test_transient_failure_returns_task_to_ready(
) -> None:
    execution = (
        build_execution()
    )

    repository = (
        RecordingExecutionRepository(
            [
                execution
            ]
        )
    )

    def processor(
        _incident_id,
    ) -> IncidentProcessingResult:
        raise (
            RetryableIncidentTaskProcessingError(
                "temporary database failure"
            )
        )

    reconciler = (
        IncidentTaskReconciler(
            execution_repository=(
                repository
            ),
            processor=processor,
            batch_size=10,
            lease_seconds=60,
        )
    )

    summary = (
        reconciler
        .reconcile_once()
    )

    assert (
        summary.retryable_failures
        == 1
    )

    assert (
        repository.retryable
        == [
            execution.task_id
        ]
    )


def test_missing_incident_marks_execution_failed(
) -> None:
    execution = (
        build_execution()
    )

    repository = (
        RecordingExecutionRepository(
            [
                execution
            ]
        )
    )

    def processor(
        incident_id,
    ) -> IncidentProcessingResult:
        raise (
            IncidentNotFoundError(
                f"Incident {incident_id} "
                "was not found."
            )
        )

    reconciler = (
        IncidentTaskReconciler(
            execution_repository=(
                repository
            ),
            processor=processor,
            batch_size=10,
            lease_seconds=60,
        )
    )

    summary = (
        reconciler
        .reconcile_once()
    )

    assert (
        summary.permanent_failures
        == 1
    )

    assert (
        repository.failed
        == [
            execution.task_id
        ]
    )
