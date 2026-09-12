from __future__ import annotations

from uuid import UUID

from app.repositories.service_repository import (
    ServiceRepository,
)


class LocalServiceCatalogGateway:
    """
    In-process adapter for the ServiceCatalogGateway contract.

    This adapter preserves the current monolithic execution
    model by delegating Service existence checks to the existing
    ServiceRepository.

    It intentionally contains no Incident persistence logic,
    HTTP client logic, FastAPI dependencies, or transaction
    management.
    """

    def __init__(
        self,
        service_repository: ServiceRepository,
    ) -> None:
        self._service_repository = (
            service_repository
        )

    def exists(
        self,
        service_id: UUID,
    ) -> bool:
        return (
            self._service_repository
            .get_by_id(
                service_id
            )
            is not None
        )