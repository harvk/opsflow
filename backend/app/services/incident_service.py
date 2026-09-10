from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.service_repository import (
    ServiceRepository,
)
from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)


# =========================================================
# INCIDENT SERVICE ERRORS
# =========================================================


class IncidentNotFoundError(
    Exception
):
    pass


class IncidentServiceReferenceError(
    Exception
):
    pass


# =========================================================
# INCIDENT SERVICE
# =========================================================


class IncidentService:
    def __init__(
        self,
        incident_repository: IncidentRepository,
        service_repository: ServiceRepository,
    ) -> None:
        self._incident_repository = (
            incident_repository
        )

        self._service_repository = (
            service_repository
        )

    # =====================================================
    # LIST / SEARCH
    # =====================================================

    def list(
        self,
        *,
        search: str | None = None,
        service_id: UUID | None = None,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        return (
            self._incident_repository
            .list(
                search=search,
                service_id=service_id,
                severity=severity,
                status=status,
                offset=offset,
                limit=limit,
            )
        )

    # =====================================================
    # GET BY ID
    # =====================================================

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        incident = (
            self._incident_repository
            .get_by_id(
                incident_id
            )
        )

        if incident is None:
            raise (
                IncidentNotFoundError(
                    f"Incident {incident_id} "
                    "was not found."
                )
            )

        return incident

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        payload: IncidentCreate,
    ) -> Incident:
        self._ensure_service_exists(
            payload.service_id
        )

        now = (
            datetime.now(
                timezone.utc
            )
        )

        resolved_at = (
            now
            if (
                payload.status
                == IncidentStatus.RESOLVED
            )
            else None
        )

        incident = (
            Incident(
                id=uuid4(),
                title=payload.title,
                service_id=(
                    payload.service_id
                ),
                severity=(
                    payload.severity
                ),
                status=(
                    payload.status
                ),
                summary=(
                    payload.summary
                ),
                assignee=(
                    payload.assignee
                ),
                started_at=(
                    payload.started_at
                    or now
                ),
                resolved_at=(
                    resolved_at
                ),
                created_at=(
                    now
                ),
                updated_at=(
                    now
                ),
            )
        )

        return (
            self._incident_repository
            .create(
                incident
            )
        )

    # =====================================================
    # UPDATE
    # =====================================================

    def update(
        self,
        incident_id: UUID,
        payload: IncidentUpdate,
    ) -> Incident:
        existing = (
            self.get_by_id(
                incident_id
            )
        )

        if (
            payload.service_id
            is not None
        ):
            self._ensure_service_exists(
                payload.service_id
            )

        updated_status = (
            payload.status
            if (
                payload.status
                is not None
            )
            else existing.status
        )

        resolved_at = (
            existing.resolved_at
        )

        if (
            existing.status
            != IncidentStatus.RESOLVED
            and updated_status
            == IncidentStatus.RESOLVED
        ):
            resolved_at = (
                datetime.now(
                    timezone.utc
                )
            )

        elif (
            existing.status
            == IncidentStatus.RESOLVED
            and updated_status
            != IncidentStatus.RESOLVED
        ):
            resolved_at = (
                None
            )

        updated = (
            replace(
                existing,
                title=(
                    payload.title
                    if (
                        payload.title
                        is not None
                    )
                    else existing.title
                ),
                service_id=(
                    payload.service_id
                    if (
                        payload.service_id
                        is not None
                    )
                    else existing.service_id
                ),
                severity=(
                    payload.severity
                    if (
                        payload.severity
                        is not None
                    )
                    else existing.severity
                ),
                status=(
                    updated_status
                ),
                summary=(
                    payload.summary
                    if (
                        payload.summary
                        is not None
                    )
                    else existing.summary
                ),
                assignee=(
                    payload.assignee
                    if (
                        payload.assignee
                        is not None
                    )
                    else existing.assignee
                ),
                started_at=(
                    payload.started_at
                    if (
                        payload.started_at
                        is not None
                    )
                    else existing.started_at
                ),
                resolved_at=(
                    resolved_at
                ),
                updated_at=(
                    datetime.now(
                        timezone.utc
                    )
                ),
            )
        )

        return (
            self._incident_repository
            .update(
                updated
            )
        )

    # =====================================================
    # DELETE
    # =====================================================

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        self.get_by_id(
            incident_id
        )

        (
            self._incident_repository
            .delete(
                incident_id
            )
        )

    # =====================================================
    # SERVICE REFERENCE VALIDATION
    # =====================================================

    def _ensure_service_exists(
        self,
        service_id: UUID,
    ) -> None:
        service = (
            self._service_repository
            .get_by_id(
                service_id
            )
        )

        if service is None:
            raise (
                IncidentServiceReferenceError(
                    f"Service {service_id} "
                    "does not exist."
                )
            )

    # =====================================================
    # LIST INCIDENTS FOR SERVICE
    # =====================================================

    def list_for_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        service = (
            self._service_repository
            .get_by_id(
                service_id
            )
        )

        if service is None:
            raise (
                IncidentNotFoundError(
                    service_id
                )
            )

        return (
            self._incident_repository
            .list_by_service(
                service_id,
                offset=offset,
                limit=limit,
            )
        )