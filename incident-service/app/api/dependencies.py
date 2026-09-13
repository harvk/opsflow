from collections.abc import (
    Generator,
)
from typing import (
    Annotated,
)

import httpx
from fastapi import (
    Depends,
)
from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    Settings,
    get_settings,
)
from app.db.session import (
    get_db_session,
)
from app.gateways.http_service_catalog_gateway import (
    HttpServiceCatalogGateway,
)
from app.gateways.service_catalog_gateway import (
    ServiceCatalogGateway,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.services.incident_service import (
    IncidentService,
)

SettingsDependency = Annotated[
    Settings,
    Depends(
        get_settings
    ),
]


DbSession = Annotated[
    Session,
    Depends(
        get_db_session
    ),
]


def get_incident_repository(
    session: DbSession,
) -> IncidentRepository:
    return (
        SqlAlchemyIncidentRepository(
            session
        )
    )


IncidentRepositoryDependency = Annotated[
    IncidentRepository,
    Depends(
        get_incident_repository
    ),
]


def get_service_catalog_gateway(
    app_settings: SettingsDependency,
) -> Generator[
    ServiceCatalogGateway,
    None,
    None,
]:
    with httpx.Client(
        timeout=(
            app_settings
            .service_catalog_timeout_seconds
        ),
    ) as client:
        yield (
            HttpServiceCatalogGateway(
                client=client,
                core_backend_url=(
                    app_settings
                    .core_backend_url
                ),
                internal_token=(
                    app_settings
                    .incident_service_token
                    .get_secret_value()
                ),
            )
        )


ServiceCatalogGatewayDependency = Annotated[
    ServiceCatalogGateway,
    Depends(
        get_service_catalog_gateway
    ),
]


def get_incident_service(
    incident_repository: (
        IncidentRepositoryDependency
    ),
    service_catalog_gateway: (
        ServiceCatalogGatewayDependency
    ),
) -> IncidentService:
    return (
        IncidentService(
            incident_repository=(
                incident_repository
            ),
            service_catalog_gateway=(
                service_catalog_gateway
            ),
        )
    )


IncidentServiceDependency = Annotated[
    IncidentService,
    Depends(
        get_incident_service
    ),
]