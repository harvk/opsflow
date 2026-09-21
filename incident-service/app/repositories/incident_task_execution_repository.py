from __future__ import annotations

from typing import (
    Protocol,
)

from app.domain.incident_task_execution import (
    IncidentTaskExecution,
)


class IncidentTaskExecutionRepository(
    Protocol
):
    """
    Persistence boundary for asynchronous Incident task
    execution state.
    """

    def list_reconcilable(
        self,
        *,
        limit: int,
    ) -> list[
        IncidentTaskExecution
    ]:
        ...

    def claim(
        self,
        execution: IncidentTaskExecution,
        *,
        lease_seconds: int,
    ) -> (
        IncidentTaskExecution
        | None
    ):
        ...

    def mark_succeeded(
        self,
        execution: IncidentTaskExecution,
        *,
        result: dict[
            str,
            object,
        ],
    ) -> None:
        ...

    def mark_retryable_failure(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        ...

    def mark_failed(
        self,
        execution: IncidentTaskExecution,
        *,
        error: str,
    ) -> None:
        ...
