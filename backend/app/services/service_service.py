from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.service import Service, ServiceStatus
from app.repositories.service_repository import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.exceptions import (
    ServiceNameConflictError,
    ServiceNotFoundError,
)


class ServiceService:
    def __init__(
        self,
        repository: ServiceRepository,
    ) -> None:
        self._repository = repository

    def list_services(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]:
        return self._repository.list(
            search=search,
            status=status,
            offset=offset,
            limit=limit,
        )

    def get_service(
        self,
        service_id: UUID,
    ) -> Service:
        service = self._repository.get_by_id(service_id)

        if service is None:
            raise ServiceNotFoundError(f"Service {service_id} was not found.")

        return service

    def create_service(
        self,
        payload: ServiceCreate,
    ) -> Service:
        existing_service = self._repository.get_by_name(payload.name)

        if existing_service is not None:
            raise ServiceNameConflictError(f"A service named '{payload.name}' already exists.")

        service = Service(
            id=uuid4(),
            name=payload.name,
            owner=payload.owner,
            status=payload.status,
            uptime=payload.uptime,
            latency_ms=payload.latency_ms,
            description=payload.description,
            region=payload.region,
            version=payload.version,
            last_deployed_at=(payload.last_deployed_at or datetime.now(UTC)),
            dependencies=payload.dependencies,
        )

        return self._repository.create(service)

    def update_service(
        self,
        service_id: UUID,
        payload: ServiceUpdate,
    ) -> Service:
        current_service = self.get_service(service_id)

        changes = payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        new_name = changes.get("name")

        if new_name:
            conflicting_service = self._repository.get_by_name(new_name)

            if conflicting_service is not None and conflicting_service.id != service_id:
                raise ServiceNameConflictError(f"A service named '{new_name}' already exists.")

        updated_service = replace(
            current_service,
            **changes,
        )

        return self._repository.update(updated_service)

    def delete_service(
        self,
        service_id: UUID,
    ) -> None:
        self.get_service(service_id)

        self._repository.delete(service_id)
