from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.domain.service import Service, ServiceStatus
from app.models.service import (
    ServiceDependencyModel,
    ServiceModel,
)


class SqlAlchemyServiceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self,
        *,
        search: str | None = None,
        status: ServiceStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Service]:
        statement = (
            select(ServiceModel)
            .options(selectinload(ServiceModel.dependencies))
            .order_by(ServiceModel.name)
            .offset(offset)
            .limit(limit)
        )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    ServiceModel.name.ilike(pattern),
                    ServiceModel.owner.ilike(pattern),
                    ServiceModel.description.ilike(pattern),
                )
            )

        if status is not None:
            statement = statement.where(
                ServiceModel.status == status
            )

        models = self._session.scalars(statement).all()

        return [
            self._to_domain(model)
            for model in models
        ]

    def get_by_id(
        self,
        service_id: UUID,
    ) -> Service | None:
        model = self._find_model(service_id)

        if model is None:
            return None

        return self._to_domain(model)

    def get_by_name(
        self,
        name: str,
    ) -> Service | None:
        statement = (
            select(ServiceModel)
            .options(selectinload(ServiceModel.dependencies))
            .where(ServiceModel.name == name)
        )

        model = self._session.scalar(statement)

        if model is None:
            return None

        return self._to_domain(model)

    def create(
        self,
        service: Service,
    ) -> Service:
        model = self._to_model(service)

        self._session.add(model)
        self._session.flush()

        return self._to_domain(model)

    def update(
        self,
        service: Service,
    ) -> Service:
        model = self._find_model(service.id)

        if model is None:
            raise LookupError(
                f"Service {service.id} does not exist."
            )

        model.name = service.name
        model.owner = service.owner
        model.status = service.status
        model.uptime = service.uptime
        model.latency_ms = service.latency_ms
        model.description = service.description
        model.region = service.region
        model.version = service.version
        model.last_deployed_at = service.last_deployed_at

        model.dependencies = [
            ServiceDependencyModel(
                dependency_name=dependency,
            )
            for dependency in service.dependencies
        ]

        self._session.flush()

        return self._to_domain(model)

    def delete(
        self,
        service_id: UUID,
    ) -> None:
        model = self._find_model(service_id)

        if model is None:
            return

        self._session.delete(model)
        self._session.flush()

    def _find_model(
        self,
        service_id: UUID,
    ) -> ServiceModel | None:
        statement = (
            select(ServiceModel)
            .options(selectinload(ServiceModel.dependencies))
            .where(ServiceModel.id == service_id)
        )

        return self._session.scalar(statement)

    @staticmethod
    def _to_model(
        service: Service,
    ) -> ServiceModel:
        return ServiceModel(
            id=service.id,
            name=service.name,
            owner=service.owner,
            status=service.status,
            uptime=service.uptime,
            latency_ms=service.latency_ms,
            description=service.description,
            region=service.region,
            version=service.version,
            last_deployed_at=service.last_deployed_at,
            dependencies=[
                ServiceDependencyModel(
                    dependency_name=dependency,
                )
                for dependency in service.dependencies
            ],
        )

    @staticmethod
    def _to_domain(
        model: ServiceModel,
    ) -> Service:
        return Service(
            id=model.id,
            name=model.name,
            owner=model.owner,
            status=model.status,
            uptime=model.uptime,
            latency_ms=model.latency_ms,
            description=model.description,
            region=model.region,
            version=model.version,
            last_deployed_at=model.last_deployed_at,
            dependencies=[
                dependency.dependency_name
                for dependency in model.dependencies
            ],
            incidents=[
                
            ]
        )