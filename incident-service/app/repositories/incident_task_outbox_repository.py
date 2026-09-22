from __future__ import annotations

from typing import (
    Protocol,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)


class IncidentTaskOutboxRepository(
    Protocol
):
    """
    Persistence boundary for Incident task publication.

    Implementations participate in the same transaction as
    Incident persistence.

    This repository does not publish to SQS.
    """

    def create(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> IncidentTaskOutboxMessage:
        ...
