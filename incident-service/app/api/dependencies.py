from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.gateways.service_catalog_gateway import (
    ServiceCatalogGateway,
)
from app.gateways.unavailable_service_catalog_gateway import (
    UnavailableServiceCatalogGateway,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.services.incident_service import IncidentService

DbSession = Annotated[
    Session,
    Depends(get_db_session),
]


def get_incident_repository(
    session: DbSession,
) -> IncidentRepository:
    return SqlAlchemyIncidentRepository(
        session
    )


IncidentRepositoryDependency = Annotated[
    IncidentRepository,
    Depends(get_incident_repository),
]


def get_service_catalog_gateway() -> ServiceCatalogGateway:
    """
    Return the current fail-closed catalog adapter.

    Tests may override this dependency. A production HTTP
    implementation replaces it in the next integration phase.
    """

    return UnavailableServiceCatalogGateway()


ServiceCatalogGatewayDependency = Annotated[
    ServiceCatalogGateway,
    Depends(get_service_catalog_gateway),
]


def get_incident_service(
    incident_repository: IncidentRepositoryDependency,
    service_catalog_gateway: ServiceCatalogGatewayDependency,
) -> IncidentService:
    return IncidentService(
        incident_repository=incident_repository,
        service_catalog_gateway=service_catalog_gateway,
    )


IncidentServiceDependency = Annotated[
    IncidentService,
    Depends(get_incident_service),
]