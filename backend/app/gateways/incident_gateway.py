from __future__ import annotations

from typing import Protocol
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


class IncidentGateway(
    Protocol
):
    """
    Application-level boundary for Incident Management.

    The Core Backend depends on this contract when it needs
    to perform Incident Management operations.

    Implementations may provide the capability through:

        an in-process IncidentService
        an HTTP-based Incident Service
        another transport introduced in the future

    This contract intentionally contains no:

        SQLAlchemy dependencies
        database session dependencies
        FastAPI dependencies
        HTTP client dependencies
        Docker/service-discovery details

    The gateway describes Incident Management capabilities,
    not how those capabilities are deployed.
    """

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
        """
        Return incidents matching the supplied filters.

        Implementations must preserve the public Incident
        Management behavior regardless of whether the
        capability executes locally or remotely.
        """

        ...

    # =====================================================
    # GET BY ID
    # =====================================================

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident:
        """
        Return one incident by identifier.

        Implementations are responsible for translating
        implementation-specific absence/failure behavior into
        the application's Incident Management error contract.
        """

        ...

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        payload: IncidentCreate,
    ) -> Incident:
        """
        Create an incident.

        The gateway receives an application request schema
        rather than an ORM model so callers are not coupled to
        Incident persistence.
        """

        ...

    # =====================================================
    # UPDATE
    # =====================================================

    def update(
        self,
        incident_id: UUID,
        payload: IncidentUpdate,
    ) -> Incident:
        """
        Update an existing incident.
        """

        ...

    # =====================================================
    # DELETE
    # =====================================================

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        """
        Delete an existing incident.
        """

        ...

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
        """
        Return incidents associated with one catalog service.
        """

        ...