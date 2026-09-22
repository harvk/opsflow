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

from app.domain.incident_task_publication import (
    IncidentTaskOutboxRecord,
)


class IncidentTaskOutboxRelayRepository(
    Protocol
):
    """
    PostgreSQL persistence boundary used only by the
    asynchronous outbox relay.
    """

    def lock_next_publishable(
        self,
        *,
        retry_before: datetime,
    ) -> (
        IncidentTaskOutboxRecord
        | None
    ):
        """
        Lock one eligible PENDING outbox row.

        Implementations must use a database lock that
        prevents concurrent relay workers from intentionally
        selecting the same row.
        """
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
