from __future__ import annotations

from typing import (
    Protocol,
)

from uuid import (
    UUID,
)

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


# =========================================================
# INCIDENT REPOSITORY CONTRACT
# =========================================================


class IncidentRepository(
    Protocol
):
    """
    Persistence-independent contract for incident storage.

    Application services depend on this protocol rather than
    directly depending on SQLAlchemy.

    Concrete implementations may include:

        SqlAlchemyIncidentRepository
        in-memory repositories used by tests
        future persistence adapters

    The protocol intentionally contains no SQLAlchemy
    imports or database implementation details.
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

        Implementations are responsible for applying:

            free-text search
            service filtering
            severity filtering
            status filtering
            pagination
        """

        ...

    # =====================================================
    # READ
    # =====================================================

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        """
        Return a single incident by identifier.

        Return None when the incident does not exist.
        """

        ...

    # =====================================================
    # CREATE
    # =====================================================

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        """
        Persist a new incident and return its domain
        representation.
        """

        ...

    # =====================================================
    # UPDATE
    # =====================================================

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        """
        Persist changes to an existing incident and return
        its updated domain representation.
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
        Remove an incident when it exists.
        """

        ...

    # =====================================================
    # SERVICE-SCOPED LIST
    # =====================================================

    def list_by_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        """
        Return incidents belonging to one service.
        """

        ...