from typing import Protocol
from uuid import UUID


class ServiceCatalogGateway(Protocol):
    """
    Minimal application boundary for Service Catalog validation.

    Incident Management stores service_id as an external
    reference. It does not own Service records and must not
    access the Core Backend's Service repository or database.

    A future adapter may satisfy this operation through an
    authenticated HTTP request.
    """

    def service_exists(
        self,
        service_id: UUID,
    ) -> bool:
        """
        Return whether the referenced catalog service exists.
        """

        ...