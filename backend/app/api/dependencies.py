from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.repositories.service_repository import (
    InMemoryServiceRepository,
)
from app.repositories.service_seed import (
    create_seed_services,
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
