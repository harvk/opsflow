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
from app.core.metrics import (
    operational_metrics,
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
from app.core.service_security_events import (
    service_security_event_logger,
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
from app.repositories.incident_task_outbox_repository import (
    IncidentTaskOutboxRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.repositories.sqlalchemy_incident_task_outbox_repository import (
    SqlAlchemyIncidentTaskOutboxRepository,
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
        operational_metrics.record_service_authentication(
            outcome="failure",
            reason="missing_credential",
        )
        service_security_event_logger.emit_authentication(
            outcome="failure",
            reason="missing_credential",
        )
        raise _service_authentication_error()

    try:
        principal = verifier.verify_token(
            credentials.credentials
        )

    except ServiceAuthenticationError as exc:
        operational_metrics.record_service_authentication(
            outcome="failure",
            reason=exc.reason.value,
        )
        service_security_event_logger.emit_authentication(
            outcome="failure",
            reason=exc.reason.value,
        )
        raise (
            _service_authentication_error()
        ) from None

    operational_metrics.record_service_authentication(
        outcome="success",
        reason="authenticated",
    )
    service_security_event_logger.emit_authentication(
        outcome="success",
        reason="authenticated",
    )

    return principal


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
            operational_metrics.record_service_authorization(
                outcome="denied",
                scope=required_scope.value,
            )
            service_security_event_logger.emit_authorization(
                outcome="blocked",
                scope=required_scope.value,
            )
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "Insufficient service permissions."
                ),
            )

        operational_metrics.record_service_authorization(
            outcome="granted",
            scope=required_scope.value,
        )
        service_security_event_logger.emit_authorization(
            outcome="success",
            scope=required_scope.value,
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
# INCIDENT TASK OUTBOX REPOSITORY
# =========================================================

def get_incident_task_outbox_repository(
    session: DbSession,
) -> IncidentTaskOutboxRepository:
    return (
        SqlAlchemyIncidentTaskOutboxRepository(
            session
        )
    )


IncidentTaskOutboxRepositoryDependency = Annotated[
    IncidentTaskOutboxRepository,
    Depends(
        get_incident_task_outbox_repository
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
    incident_task_outbox_repository: (
        IncidentTaskOutboxRepositoryDependency
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
            incident_task_outbox_repository=(
                incident_task_outbox_repository
            ),
        )
    )


IncidentServiceDependency = Annotated[
    IncidentService,
    Depends(
        get_incident_service
    ),
]
