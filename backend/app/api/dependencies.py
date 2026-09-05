from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session

from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.service_repository import (
    ServiceRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.repositories.sqlalchemy_service_repository import (
    SqlAlchemyServiceRepository,
)

from app.services.incident_service import (
    IncidentService,
)
from app.services.service_service import (
    ServiceService,
)


DbSession = Annotated[
    Session,
    Depends(get_db_session),
]


# ---------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------

def get_service_repository(
    session: DbSession,
) -> ServiceRepository:
    return SqlAlchemyServiceRepository(
        session
    )


ServiceRepositoryDependency = Annotated[
    ServiceRepository,
    Depends(get_service_repository),
]


def get_service_service(
    repository: ServiceRepositoryDependency,
) -> ServiceService:
    return ServiceService(
        repository
    )


ServiceServiceDependency = Annotated[
    ServiceService,
    Depends(get_service_service),
]


# ---------------------------------------------------------
# Incident dependencies
# ---------------------------------------------------------

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


def get_incident_service(
    incident_repository: IncidentRepositoryDependency,
    service_repository: ServiceRepositoryDependency,
) -> IncidentService:
    return IncidentService(
        incident_repository=incident_repository,
        service_repository=service_repository,
    )


IncidentServiceDependency = Annotated[
    IncidentService,
    Depends(get_incident_service),
]