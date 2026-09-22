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
from sqlalchemy.dialects.postgresql import (
    insert,
)
from sqlalchemy.orm import (
    Session,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.domain.incident_task_completion import (
    IncidentTaskCompletionOutboxMessage,
)
from app.domain.incident_task_completion_publication import (
    IncidentTaskCompletionOutboxRecord,
)
from app.models.incident_task_completion_outbox import (
    IncidentTaskCompletionOutboxModel,
)


class IncidentTaskCompletionOutboxNotFoundError(
    RuntimeError
):
    """
    Raised when completion-event publication state references
    an outbox row that no longer exists.
    """


class IncidentTaskCompletionOutboxCollisionError(
    RuntimeError
):
    """
    Raised when a task_id already belongs to a completion
    event for a different Incident or correlation identity.
    """


class SqlAlchemyIncidentTaskCompletionOutboxRepository:
    """
    SQLAlchemy implementation of completion-event outbox
    persistence and relay boundaries.

    create() is idempotent by task_id. This is required when
    PostgreSQL commits successfully but the reconciler later
    fails to mark the DynamoDB execution SUCCEEDED and must
    retry the same task.

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
        message: IncidentTaskCompletionOutboxMessage,
    ) -> IncidentTaskCompletionOutboxMessage:
        statement = (
            insert(
                IncidentTaskCompletionOutboxModel
            )
            .values(
                id=message.id,
                event_id=message.event_id,
                incident_id=(
                    message.incident_id
                ),
                task_id=message.task_id,
                correlation_id=(
                    message.correlation_id
                ),
                schema_version=(
                    message.schema_version
                ),
                event_type=(
                    message.event_type
                ),
                status=(
                    message.status.value
                ),
                acknowledged_at=(
                    message.acknowledged_at
                ),
                occurred_at=(
                    message.occurred_at
                ),
                publication_status=(
                    "PENDING"
                ),
                publish_attempts=0,
                created_at=(
                    message.occurred_at
                ),
                updated_at=(
                    message.occurred_at
                ),
                published_at=None,
                last_error=None,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    "task_id",
                ]
            )
            .returning(
                IncidentTaskCompletionOutboxModel.id
            )
        )

        inserted_id = (
            self._session
            .execute(
                statement
            )
            .scalar_one_or_none()
        )

        if inserted_id is not None:
            return message

        existing = (
            self._session
            .scalar(
                select(
                    IncidentTaskCompletionOutboxModel
                )
                .where(
                    IncidentTaskCompletionOutboxModel
                    .task_id
                    == message.task_id
                )
            )
        )

        if existing is None:
            raise RuntimeError(
                "Completion outbox conflict was reported "
                "but the existing task row could not be "
                "loaded."
            )

        if (
            existing.incident_id
            != message.incident_id
            or existing.correlation_id
            != message.correlation_id
        ):
            raise (
                IncidentTaskCompletionOutboxCollisionError(
                    "Existing completion outbox task identity "
                    "does not match the incoming Incident "
                    "completion event."
                )
            )

        return (
            self._to_domain_message(
                existing
            )
        )

    def lock_next_publishable(
        self,
        *,
        retry_before: datetime,
    ) -> (
        IncidentTaskCompletionOutboxRecord
        | None
    ):
        statement = (
            select(
                IncidentTaskCompletionOutboxModel
            )
            .where(
                IncidentTaskCompletionOutboxModel
                .publication_status
                == "PENDING"
            )
            .where(
                or_(
                    IncidentTaskCompletionOutboxModel
                    .publish_attempts
                    == 0,
                    IncidentTaskCompletionOutboxModel
                    .updated_at
                    <= retry_before,
                )
            )
            .order_by(
                IncidentTaskCompletionOutboxModel
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
            IncidentTaskCompletionOutboxRecord(
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
    ) -> IncidentTaskCompletionOutboxModel:
        model = (
            self._session.get(
                IncidentTaskCompletionOutboxModel,
                outbox_id,
            )
        )

        if model is None:
            raise (
                IncidentTaskCompletionOutboxNotFoundError(
                    "Incident task completion outbox row "
                    f"{outbox_id} was not found."
                )
            )

        return model

    @staticmethod
    def _to_domain_message(
        model: IncidentTaskCompletionOutboxModel,
    ) -> IncidentTaskCompletionOutboxMessage:
        return (
            IncidentTaskCompletionOutboxMessage(
                id=model.id,
                event_id=model.event_id,
                incident_id=(
                    model.incident_id
                ),
                task_id=model.task_id,
                correlation_id=(
                    model.correlation_id
                ),
                schema_version=(
                    model.schema_version
                ),
                event_type=(
                    model.event_type
                ),
                status=(
                    IncidentStatus(
                        model.status
                    )
                ),
                acknowledged_at=(
                    model.acknowledged_at
                ),
                occurred_at=(
                    model.occurred_at
                ),
            )
        )
