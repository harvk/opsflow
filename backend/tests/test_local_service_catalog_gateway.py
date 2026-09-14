from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

from app.gateways.local_service_catalog_gateway import (
    LocalServiceCatalogGateway,
)
from app.repositories.service_repository import (
    ServiceRepository,
)


class StubServiceRepository:
    def __init__(
        self,
        existing_service_ids: set[UUID],
    ) -> None:
        self._existing_service_ids = (
            existing_service_ids
        )

    def get_by_id(
        self,
        service_id: UUID,
    ) -> object | None:
        if (
            service_id
            in self._existing_service_ids
        ):
            return object()

        return None


def test_exists_returns_true_for_known_service(
) -> None:
    service_id = uuid4()

    repository = (
        StubServiceRepository(
            {
                service_id,
            }
        )
    )

    gateway = (
        LocalServiceCatalogGateway(
            cast(
                ServiceRepository,
                repository,
            )
        )
    )

    assert (
        gateway.exists(
            service_id
        )
        is True
    )


def test_exists_returns_false_for_unknown_service(
) -> None:
    gateway = (
        LocalServiceCatalogGateway(
            cast(
                ServiceRepository,
                StubServiceRepository(
                    set()
                ),
            )
        )
    )

    assert (
        gateway.exists(
            uuid4()
        )
        is False
    )