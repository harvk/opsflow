from __future__ import annotations

from typing import Protocol
from uuid import UUID


class ServiceCatalogGateway(
    Protocol
):
    """
    Application-level boundary for Service Catalog lookups.

    Incident Management depends on this contract when it must
    validate a Service reference.

    Implementations may resolve the reference through:

        the current in-process ServiceRepository
        a future HTTP-based Service Catalog
        another transport introduced later

    The contract intentionally exposes only the capability
    Incident Management currently requires. It does not expose
    Service persistence or return Service domain objects.
    """

    def exists(
        self,
        service_id: UUID,
    ) -> bool:
        """
        Return True when the Service Catalog contains the
        supplied Service identifier.
        """

        ...
