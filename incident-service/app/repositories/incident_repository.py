from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


class IncidentRepository(Protocol):
    """
    Persistence-independent contract for Incident storage.

    Application services depend on this protocol instead of a
    SQLAlchemy implementation or database session.
    """

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
        """

        ...

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        """
        Return an Incident or None when it does not exist.
        """

        ...

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        """
        Persist and return a new Incident.
        """

        ...

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        """
        Persist and return an updated Incident.
        """

        ...

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        """
        Delete an Incident when it exists.
        """

        ...

    def list_by_service(
        self,
        service_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Incident]:
        """
        Return incidents associated with an external Service ID.
        """

        ...