from __future__ import annotations

from datetime import (
    datetime,
)
from typing import (
    Protocol,
)
from uuid import (
    UUID,
)

from app.domain.incident_task_completion_publication import (
    IncidentTaskCompletionOutboxRecord,
)


class IncidentTaskCompletionOutboxRelayRepository(
    Protocol
):
    """
    PostgreSQL persistence boundary used by the completion
    event outbox relay.
    """

    def lock_next_publishable(
        self,
        *,
        retry_before: datetime,
    ) -> (
        IncidentTaskCompletionOutboxRecord
        | None
    ):
        ...

    def mark_published(
        self,
        outbox_id: UUID,
        *,
        published_at: datetime,
    ) -> None:
        ...

    def mark_publish_failed(
        self,
        outbox_id: UUID,
        *,
        failed_at: datetime,
        error: str,
    ) -> None:
        ...
