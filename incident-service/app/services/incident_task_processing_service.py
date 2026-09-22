from __future__ import annotations

from dataclasses import (
    dataclass,
    replace,
)
from datetime import (
    UTC,
    datetime,
)
from uuid import (
    UUID,
)

from app.domain.incident import (
    IncidentStatus,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.services.exceptions import (
    IncidentNotFoundError,
)


@dataclass(
    frozen=True,
    slots=True,
)
class IncidentProcessingResult:
    """
    Result of applying asynchronous Incident processing to
    PostgreSQL business state.
    """

    incident_id: UUID

    status: IncidentStatus

    changed: bool

    acknowledged_at: (
        datetime
        | None
    )


class IncidentTaskProcessingService:
    """
    Apply the business effect of an asynchronous Incident
    processing task.

    The operation is deliberately naturally idempotent.

    OPEN:
        -> INVESTIGATING
        -> acknowledged if needed

    INVESTIGATING:
        -> remains INVESTIGATING
        -> acknowledged if needed

    MONITORING / RESOLVED:
        -> never regressed by asynchronous processing
    """

    def __init__(
        self,
        incident_repository: IncidentRepository,
    ) -> None:
        self._incident_repository = (
            incident_repository
        )

    def process(
        self,
        incident_id: UUID,
    ) -> IncidentProcessingResult:
        existing = (
            self._incident_repository
            .get_by_id(
                incident_id
            )
        )

        if existing is None:
            raise IncidentNotFoundError(
                f"Incident {incident_id} was not found."
            )

        target_status = (
            IncidentStatus.INVESTIGATING
            if (
                existing.status
                is IncidentStatus.OPEN
            )
            else existing.status
        )

        target_acknowledged_at = (
            existing.acknowledged_at
        )

        if (
            existing.status
            in {
                IncidentStatus.OPEN,
                IncidentStatus.INVESTIGATING,
            }
            and (
                target_acknowledged_at
                is None
            )
        ):
            target_acknowledged_at = (
                datetime.now(
                    UTC
                )
            )

        changed = (
            target_status
            is not existing.status
            or (
                target_acknowledged_at
                != existing.acknowledged_at
            )
        )

        if not changed:
            return (
                IncidentProcessingResult(
                    incident_id=(
                        existing.id
                    ),
                    status=(
                        existing.status
                    ),
                    changed=False,
                    acknowledged_at=(
                        existing
                        .acknowledged_at
                    ),
                )
            )

        updated = replace(
            existing,
            status=(
                target_status
            ),
            acknowledged_at=(
                target_acknowledged_at
            ),
            updated_at=(
                datetime.now(
                    UTC
                )
            ),
        )

        persisted = (
            self._incident_repository
            .update(
                updated
            )
        )

        return (
            IncidentProcessingResult(
                incident_id=(
                    persisted.id
                ),
                status=(
                    persisted.status
                ),
                changed=True,
                acknowledged_at=(
                    persisted
                    .acknowledged_at
                ),
            )
        )
