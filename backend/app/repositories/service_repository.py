from typing import Protocol
from uuid import UUID

from app.domain.service import Service, ServiceStatus


class ServiceRepository(Protocol):
    def list(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]: ...

    def get_by_id(
        self,
        service_id: UUID,
    ) -> Service | None: ...

    def get_by_name(
        self,
        name: str,
    ) -> Service | None: ...

    def create(
        self,
        service: Service,
    ) -> Service: ...

    def update(
        self,
        service: Service,
    ) -> Service: ...

    def delete(
        self,
        service_id: UUID,
    ) -> None: ...


class InMemoryServiceRepository:
    def __init__(
        self,
        initial_services: list[Service] | None = None,
    ) -> None:
        self._services: dict[UUID, Service] = {}

        if initial_services:
            for service in initial_services:
                self._services[service.id] = service

    def list(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]:
        services = list(self._services.values())

        if search:
            normalized_search = search.strip().lower()

            services = [
                service
                for service in services
                if normalized_search in service.name.lower()
                or normalized_search in service.owner.lower()
                or normalized_search in service.region.lower()
            ]

        if status:
            services = [service for service in services if service.status == status]

        services.sort(key=lambda service: service.name.lower())

        return services[offset : offset + limit]

    def get_by_id(
        self,
        service_id: UUID,
    ) -> Service | None:
        return self._services.get(service_id)

    def get_by_name(
        self,
        name: str,
    ) -> Service | None:
        normalized_name = name.strip().lower()

        return next(
            (
                service
                for service in self._services.values()
                if service.name.lower() == normalized_name
            ),
            None,
        )

    def create(
        self,
        service: Service,
    ) -> Service:
        self._services[service.id] = service

        return service

    def update(
        self,
        service: Service,
    ) -> Service:
        self._services[service.id] = service

        return service

    def delete(
        self,
        service_id: UUID,
    ) -> None:
        self._services.pop(service_id, None)
