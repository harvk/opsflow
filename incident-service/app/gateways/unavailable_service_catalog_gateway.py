from uuid import UUID

from app.services.exceptions import (
    ServiceCatalogUnavailableError,
)


class UnavailableServiceCatalogGateway:
    """
    Fail-closed placeholder used until the production Service
    Catalog HTTP adapter is configured.

    It never treats an unvalidated Service ID as valid.
    """

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        raise ServiceCatalogUnavailableError(
            "Service Catalog validation is unavailable. "
            f"Could not validate Service {service_id}."
        )