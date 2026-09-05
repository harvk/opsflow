from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.service import Service, ServiceStatus
from app.repositories.service_repository import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.exceptions import (
    ServiceNameConflictError,
    ServiceNotFoundError
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
            incidents=[]
        )

        return self._repository.create(service)

    def update_service(
        self,
        service_id: UUID,
        payload: ServiceUpdate,
    ) -> Service:
        existing = self._repository.get_by_id(
            service_id
        )

        if existing is None:
            raise ServiceNotFoundError(
                f"Service {service_id} was not found."
            )

        changes = payload.model_dump(
            exclude_unset=True,
        )

        if "name" in changes:
            existing_with_name = (
                self._repository.get_by_name(
                    changes["name"]
                )
            )

            if (
                existing_with_name is not None
                and existing_with_name.id != service_id
            ):
                raise ServiceNameConflictError(
                    f'A service named "{changes["name"]}" '
                    "already exists."
                )

        updated = replace(
            existing,
            **changes,
        )

        return self._repository.update(
            updated
        )

    def delete_service(
        self,
        service_id: UUID,
    ) -> None:
        self.get_service(service_id)

        self._repository.delete(service_id)
