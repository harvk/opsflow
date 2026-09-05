from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.repositories.incident_repository import (
    InMemoryIncidentRepository,
)
from app.repositories.incident_seed import (
    create_seed_incidents,
)
from app.repositories.service_repository import (
    InMemoryServiceRepository,
)
from app.repositories.service_seed import (
    create_seed_services,
)
from app.services.incident_service import (
    IncidentService,
)
from app.services.service_service import (
    ServiceService,
)


@lru_cache
def get_service_repository() -> InMemoryServiceRepository:
    return InMemoryServiceRepository(create_seed_services())


def get_service_service(
    repository: Annotated[
        InMemoryServiceRepository,
        Depends(get_service_repository),
    ],
) -> ServiceService:
    return ServiceService(repository)


@lru_cache
def get_incident_repository() -> InMemoryIncidentRepository:
    return InMemoryIncidentRepository(create_seed_incidents())


def get_incident_service(
    incident_repository: Annotated[
        InMemoryIncidentRepository,
        Depends(get_incident_repository),
    ],
    service_repository: Annotated[
        InMemoryServiceRepository,
        Depends(get_service_repository),
    ],
) -> IncidentService:
    return IncidentService(
        incident_repository,
        service_repository,
    )
