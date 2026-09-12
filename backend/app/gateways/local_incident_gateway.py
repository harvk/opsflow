from __future__ import annotations

from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)

from app.schemas.incident import (
    IncidentCreate,
    IncidentUpdate,
)

from app.services.incident_service import (
    IncidentService,
)


class LocalIncidentGateway:
    """
    In-process adapter for the IncidentGateway contract.

    This adapter preserves the current monolithic execution
    model by delegating Incident Management operations to the
    existing IncidentService.

    It intentionally contains no:

        SQLAlchemy logic
        database session management
        FastAPI dependencies
        HTTP client logic
        business-rule duplication

    When Incident Management is extracted into an independent
    service, the Core Backend will be able to replace this
    adapter with a remote implementation without changing
    callers that depend on the IncidentGateway contract.
    """

    def __init__(
        self,
        incident_service: IncidentService,
    ) -> None:
        self._incident_service = (
            incident_service
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
            self._incident_service
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
        return (
            self._incident_service
            .get_by_id(
                incident_id
            )
        )

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        payload: IncidentCreate,
    ) -> Incident:
        return (
            self._incident_service
            .create(
                payload
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
        return (
            self._incident_service
            .update(
                incident_id,
                payload,
            )
        )

    # =====================================================
    # DELETE
    # =====================================================

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        (
            self._incident_service
            .delete(
                incident_id
            )
        )

    # =====================================================
    # SERVICE-SCOPED LIST
    # =====================================================

    def list_for_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        return (
            self._incident_service
            .list_for_service(
                service_id,
                offset=offset,
                limit=limit,
            )
        )