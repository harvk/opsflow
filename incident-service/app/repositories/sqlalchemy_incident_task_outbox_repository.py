from __future__ import annotations

from sqlalchemy.orm import (
    Session,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.models.incident_task_outbox import (
    IncidentTaskOutboxModel,
)


class SqlAlchemyIncidentTaskOutboxRepository:
    """
    SQLAlchemy implementation of the Incident task outbox
    repository.

    This adapter intentionally flushes but does not commit.

    Transaction ownership remains at the request database
    session boundary so Incident creation and task issuance
    remain atomic.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = (
            session
        )

    def create(
        self,
        message: IncidentTaskOutboxMessage,
    ) -> IncidentTaskOutboxMessage:
        model = (
            IncidentTaskOutboxModel(
                id=message.id,
                task_id=message.task_id,
                incident_id=(
                    message.incident_id
                ),
                schema_version=(
                    message.schema_version
                ),
                task_type=(
                    message.task_type
                ),
                idempotency_key=(
                    message.idempotency_key
                ),
                correlation_id=(
                    message.correlation_id
                ),
                causation_id=(
                    message.causation_id
                ),
                payload=message.payload,
                metadata_=message.metadata,
                publication_status=(
                    "PENDING"
                ),
                publish_attempts=0,
                created_at=(
                    message.created_at
                ),
                updated_at=(
                    message.created_at
                ),
                published_at=None,
                last_error=None,
            )
        )

        self._session.add(
            model
        )

        self._session.flush()

        return message
