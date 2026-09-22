from __future__ import annotations

from typing import (
    Protocol,
)

from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)


class IncidentTaskCompletionOutboxRepository(
    Protocol
):
    """
    Transactional persistence boundary for Incident task
    completion events.

    Implementations participate in the same PostgreSQL
    transaction as Incident reconciliation.
    """

    def create(
        self,
        message: IncidentTaskCompletionOutboxMessage,
    ) -> IncidentTaskCompletionOutboxMessage:
        ...
