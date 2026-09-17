from collections.abc import (
    Callable,
    Generator,
)
from functools import (
    lru_cache,
)
from typing import (
    Annotated,
)

import httpx
from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    Settings,
    get_settings,
)
from app.core.service_identity import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ServiceAuthenticationError,
    ServicePrincipal,
    ServiceScope,
    ServiceTokenVerifier,
)
from app.core.service_identity_loader import (
    build_service_token_verifier,
)
from app.core.service_token_provider import (
    get_service_token_provider,
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
# SERVICE-IDENTITY AUTHENTICATION
# =========================================================

service_bearer_scheme = HTTPBearer(
    scheme_name="ServiceBearer",
    description=(
        "Short-lived OpsFlow RS256 service credential."
    ),
    bearerFormat="JWT",
    auto_error=False,
)

ServiceBearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(
        service_bearer_scheme
    ),
]


@lru_cache(
    maxsize=1,
)
def get_service_token_verifier(
) -> ServiceTokenVerifier:
    """
    Build one process-local verifier from trusted settings.

    The cached verifier parses public keys once rather than
    repeating PEM and RSA validation for every request.
    """

    return build_service_token_verifier(
        get_settings()
    )


ServiceTokenVerifierDependency = Annotated[
    ServiceTokenVerifier,
    Depends(
        get_service_token_verifier
    ),
]


def _service_authentication_error(
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_401_UNAUTHORIZED
        ),
        detail=(
            INVALID_SERVICE_CREDENTIALS_MESSAGE
        ),
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def authenticate_service(
    credentials: ServiceBearerCredentials,
    verifier: ServiceTokenVerifierDependency,
) -> ServicePrincipal:
    """
    Authenticate one RS256 bearer service credential.

    Missing, malformed, expired, and otherwise invalid
    credentials deliberately share one public response.
    """

    if credentials is None:
        raise _service_authentication_error()

    try:
        return verifier.verify_token(
            credentials.credentials
        )

    except ServiceAuthenticationError:
        raise (
            _service_authentication_error()
        ) from None


AuthenticatedServicePrincipal = Annotated[
    ServicePrincipal,
    Depends(
        authenticate_service
    ),
]


ScopeDependency = Callable[
    [ServicePrincipal],
    ServicePrincipal,
]


def require_service_scope(
    required_scope: ServiceScope,
) -> ScopeDependency:
    """
    Create a dependency enforcing one registered scope.
    """

    def require_scope(
        principal: AuthenticatedServicePrincipal,
    ) -> ServicePrincipal:
        if required_scope not in principal.scopes:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "Insufficient service permissions."
                ),
            )

        return principal

    return require_scope


require_incidents_read = require_service_scope(
    ServiceScope.INCIDENTS_READ
)

require_incidents_write = require_service_scope(
    ServiceScope.INCIDENTS_WRITE
)

IncidentReadPrincipal = Annotated[
    ServicePrincipal,
    Depends(
        require_incidents_read
    ),
]

IncidentWritePrincipal = Annotated[
    ServicePrincipal,
    Depends(
        require_incidents_write
    ),
]


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
                service_token_provider=(
                    get_service_token_provider()
                ),
                core_backend_audience=(
                    app_settings
                    .core_backend_audience
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
