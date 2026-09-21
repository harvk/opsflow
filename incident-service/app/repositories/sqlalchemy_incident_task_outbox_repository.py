from __future__ import annotations

from datetime import (
    datetime,
)
from uuid import (
    UUID,
)

from sqlalchemy import (
    or_,
    select,
)
from sqlalchemy.orm import (
    Session,
)

from app.domain.incident_task import (
    IncidentTaskOutboxMessage,
)
from app.domain.incident_task_publication import (
    IncidentTaskOutboxRecord,
)
from app.models.incident_task_outbox import (
    IncidentTaskOutboxModel,
)


class IncidentTaskOutboxNotFoundError(
    RuntimeError
):
    """
    Raised when relay publication state references an
    outbox row that no longer exists.
    """


class SqlAlchemyIncidentTaskOutboxRepository:
    """
    SQLAlchemy implementation of both Incident outbox
    persistence boundaries.

    Incident creation:
        create()

    Asynchronous relay:
        lock_next_publishable()
        mark_published()
        mark_publish_failed()

    Transaction ownership remains outside this repository.
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

    def lock_next_publishable(
        self,
        *,
        retry_before: datetime,
    ) -> (
        IncidentTaskOutboxRecord
        | None
    ):
        statement = (
            select(
                IncidentTaskOutboxModel
            )
            .where(
                IncidentTaskOutboxModel
                .publication_status
                == "PENDING"
            )
            .where(
                or_(
                    IncidentTaskOutboxModel
                    .publish_attempts
                    == 0,
                    IncidentTaskOutboxModel
                    .updated_at
                    <= retry_before,
                )
            )
            .order_by(
                IncidentTaskOutboxModel
                .created_at
                .asc()
            )
            .limit(
                1
            )
            .with_for_update(
                skip_locked=True
            )
        )

        model = (
            self._session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return (
            IncidentTaskOutboxRecord(
                message=(
                    self
                    ._to_domain_message(
                        model
                    )
                ),
                publish_attempts=(
                    model.publish_attempts
                ),
            )
        )

    def mark_published(
        self,
        outbox_id: UUID,
        *,
        published_at: datetime,
    ) -> None:
        model = (
            self._require_model(
                outbox_id
            )
        )

        model.publication_status = (
            "PUBLISHED"
        )

        model.publish_attempts += 1

        model.published_at = (
            published_at
        )

        model.updated_at = (
            published_at
        )

        model.last_error = None

        self._session.flush()

    def mark_publish_failed(
        self,
        outbox_id: UUID,
        *,
        failed_at: datetime,
        error: str,
    ) -> None:
        model = (
            self._require_model(
                outbox_id
            )
        )

        model.publication_status = (
            "PENDING"
        )

        model.publish_attempts += 1

        model.updated_at = (
            failed_at
        )

        model.last_error = (
            error[
                :2000
            ]
        )

        self._session.flush()

    def _require_model(
        self,
        outbox_id: UUID,
    ) -> IncidentTaskOutboxModel:
        model = (
            self._session.get(
                IncidentTaskOutboxModel,
                outbox_id,
            )
        )

        if model is None:
            raise (
                IncidentTaskOutboxNotFoundError(
                    "Incident task outbox row "
                    f"{outbox_id} was not found."
                )
            )

        return model

    @staticmethod
    def _to_domain_message(
        model: IncidentTaskOutboxModel,
    ) -> IncidentTaskOutboxMessage:
        return (
            IncidentTaskOutboxMessage(
                id=model.id,
                task_id=model.task_id,
                incident_id=(
                    model.incident_id
                ),
                schema_version=(
                    model.schema_version
                ),
                task_type=(
                    model.task_type
                ),
                idempotency_key=(
                    model.idempotency_key
                ),
                correlation_id=(
                    model.correlation_id
                ),
                causation_id=(
                    model.causation_id
                ),
                payload=dict(
                    model.payload
                ),
                metadata=dict(
                    model.metadata_
                ),
                created_at=(
                    model.created_at
                ),
            )
        )
