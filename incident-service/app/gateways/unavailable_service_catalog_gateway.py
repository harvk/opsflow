from uuid import UUID

from app.services.exceptions import (
    ServiceCatalogUnavailableError,
)


class UnavailableServiceCatalogGateway:
    """
    Explicit fail-closed Service Catalog adapter.

    This remains useful for tests and intentionally isolated
    deployments, but it is no longer the production default.
    """

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        raise ServiceCatalogUnavailableError(
            "Service Catalog validation is unavailable. "
            f"Could not validate Service {service_id}."
        )