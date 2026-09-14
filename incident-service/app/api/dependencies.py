from collections.abc import (
    Generator,
)
from secrets import (
    compare_digest,
)
from typing import (
    Annotated,
)

import httpx
from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
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


# =========================================================
# INTERNAL SERVICE AUTHENTICATION
# =========================================================

InternalServiceTokenHeader = Annotated[
    str | None,
    Header(
        alias=(
            "X-OpsFlow-Internal-Token"
        ),
    ),
]


def require_core_backend_token(
    app_settings: SettingsDependency,
    supplied_token: (
        InternalServiceTokenHeader
    ) = None,
) -> None:
    """
    Authenticate requests originating from Core Backend.

    Missing and incorrect credentials deliberately produce
    the same response so the endpoint does not reveal which
    part of the credential check failed.
    """

    expected_token = (
        app_settings
        .incident_service_token
        .get_secret_value()
    )

    token_is_valid = (
        supplied_token is not None
        and compare_digest(
            supplied_token.encode(
                "utf-8"
            ),
            expected_token.encode(
                "utf-8"
            ),
        )
    )

    if not token_is_valid:
        raise HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Invalid internal service credentials."
            ),
        )


# =========================================================
# DATABASE SESSION
# =========================================================

DbSession = Annotated[
    Session,
    Depends(
        get_db_session
    ),
]


# =========================================================
# INCIDENT REPOSITORY
# =========================================================

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


# =========================================================
# SERVICE CATALOG GATEWAY
# =========================================================

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


# =========================================================
# INCIDENT SERVICE
# =========================================================

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