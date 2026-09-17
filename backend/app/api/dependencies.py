from __future__ import annotations

import logging
from collections.abc import (
    Callable,
)
from functools import (
    lru_cache,
)
from typing import (
    Annotated,
    cast,
)

import boto3
import httpx
from botocore.config import (
    Config,
)
from botocore.exceptions import (
    BotoCoreError,
)
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from sqlalchemy.orm import (
    Session,
)

from app.core.auth_error_codes import (
    AuthErrorCode,
    auth_error_headers,
)
from app.core.auth_response_messages import (
    ACCESS_CREDENTIALS_INVALID_MESSAGE,
)
from app.core.circuit_breaker import (
    CircuitBreaker,
)
from app.core.config import (
    settings,
)
from app.core.login_throttle import (
    InMemoryLoginThrottle,
    LoginThrottle,
)
from app.core.metrics import (
    operational_metrics,
)
from app.core.password_reset_links import (
    PasswordResetLinkBuilder,
)
from app.core.password_reset_throttle import (
    InMemoryPasswordResetThrottle,
    PasswordResetThrottle,
)
from app.core.security_events import (
    security_event_logger,
)
from app.core.service_identity import (
    ServiceScope,
)
from app.core.service_identity_provider import (
    get_service_token_provider,
)
from app.core.service_token_verifier import (
    INVALID_SERVICE_CREDENTIALS_MESSAGE,
    ServiceAuthenticationError,
    ServicePrincipal,
    ServiceTokenVerifier,
)
from app.core.service_token_verifier_loader import (
    build_service_token_verifier,
)
from app.db.session import (
    get_db_session,
)
from app.domain.authorization import (
    Permission,
)
from app.domain.user import (
    User,
)
from app.gateways.http_incident_gateway import (
    HttpIncidentGateway,
)
from app.gateways.incident_gateway import (
    IncidentGateway,
)
from app.gateways.local_incident_gateway import (
    LocalIncidentGateway,
)
from app.gateways.local_service_catalog_gateway import (
    LocalServiceCatalogGateway,
)
from app.gateways.service_catalog_gateway import (
    ServiceCatalogGateway,
)
from app.infrastructure.aws.ses_password_reset_delivery import (
    SesClient,
    SesPasswordResetDelivery,
)
from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)
from app.repositories.incident_repository import (
    IncidentRepository,
)
from app.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from app.repositories.service_repository import (
    ServiceRepository,
)
from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)
from app.repositories.sqlalchemy_incident_repository import (
    SqlAlchemyIncidentRepository,
)
from app.repositories.sqlalchemy_password_reset_token_repository import (
    SqlAlchemyPasswordResetTokenRepository,
)
from app.repositories.sqlalchemy_service_repository import (
    SqlAlchemyServiceRepository,
)
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService,
)
from app.services.authorization_service import (
    AuthorizationService,
    PermissionDeniedError,
)
from app.services.incident_service import (
    IncidentService,
)
from app.services.password_reset_delivery import (
    PasswordResetDelivery,
    PasswordResetDeliveryError,
)
from app.services.password_reset_delivery_coordinator import (
    PasswordResetDeliveryCoordinator,
)
from app.services.password_reset_service import (
    PasswordResetService,
)
from app.services.service_service import (
    ServiceService,
)

authorization_service = (
    AuthorizationService()
)


# =========================================================
# SHARED DATABASE DEPENDENCY
# =========================================================

DbSession = Annotated[
    Session,
    Depends(
        get_db_session
    ),
]


# =========================================================
# INTERNAL SERVICE AUTHENTICATION
# =========================================================

incident_service_bearer_scheme = HTTPBearer(
    scheme_name="IncidentServiceBearer",
    description=(
        "Short-lived Incident Service RS256 credential."
    ),
    bearerFormat="JWT",
    auto_error=False,
)

IncidentServiceBearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(
        incident_service_bearer_scheme
    ),
]


@lru_cache(maxsize=1)
def get_incident_service_token_verifier(
) -> ServiceTokenVerifier:
    return build_service_token_verifier(
        settings
    )


IncidentServiceTokenVerifierDependency = Annotated[
    ServiceTokenVerifier,
    Depends(
        get_incident_service_token_verifier
    ),
]


def _incident_service_authentication_error(
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_SERVICE_CREDENTIALS_MESSAGE,
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )


def authenticate_incident_service(
    credentials: IncidentServiceBearerCredentials,
    verifier: IncidentServiceTokenVerifierDependency,
) -> ServicePrincipal:
    """
    Authenticate requests originating from the Incident Service.

    Missing and incorrect credentials deliberately produce the
    same response.
    """

    if credentials is None:
        raise _incident_service_authentication_error()

    try:
        return verifier.verify_token(
            credentials.credentials
        )

    except ServiceAuthenticationError:
        raise (
            _incident_service_authentication_error()
        ) from None


AuthenticatedIncidentServicePrincipal = Annotated[
    ServicePrincipal,
    Depends(
        authenticate_incident_service
    ),
]


def require_services_read(
    principal: AuthenticatedIncidentServicePrincipal,
) -> ServicePrincipal:
    if ServiceScope.SERVICES_READ not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient service permissions.",
        )

    return principal


# =========================================================
# OAUTH2
# =========================================================

oauth2_scheme = (
    OAuth2PasswordBearer(
        tokenUrl=(
            "api/v1/auth/token"
        ),
        auto_error=False,
    )
)


# =========================================================
# PERMISSIONS
# =========================================================

def require_permission(
    permission: Permission,
) -> Callable[
    ...,
    User,
]:
    def permission_dependency(
        current_user: CurrentUser,
    ) -> User:
        try:
            (
                authorization_service
                .require_permission(
                    current_user,
                    permission,
                )
            )

        except (
            PermissionDeniedError
        ) as exc:
            raise HTTPException(
                status_code=(
                    status
                    .HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have permission "
                    "to perform this action."
                ),
            ) from exc

        return current_user

    return permission_dependency


# =========================================================
# SERVICE DEPENDENCIES
# =========================================================

def get_service_repository(
    session: DbSession,
) -> ServiceRepository:
    return (
        SqlAlchemyServiceRepository(
            session
        )
    )


ServiceRepositoryDependency = (
    Annotated[
        ServiceRepository,
        Depends(
            get_service_repository
        ),
    ]
)


def get_service_service(
    repository: (
        ServiceRepositoryDependency
    ),
) -> ServiceService:
    return (
        ServiceService(
            repository
        )
    )


ServiceServiceDependency = (
    Annotated[
        ServiceService,
        Depends(
            get_service_service
        ),
    ]
)


# =========================================================
# SERVICE CATALOG GATEWAY DEPENDENCY
# =========================================================

def get_service_catalog_gateway(
    service_repository: (
        ServiceRepositoryDependency
    ),
) -> ServiceCatalogGateway:
    return (
        LocalServiceCatalogGateway(
            service_repository
        )
    )


ServiceCatalogGatewayDependency = (
    Annotated[
        ServiceCatalogGateway,
        Depends(
            get_service_catalog_gateway
        ),
    ]
)


# =========================================================
# INCIDENT DEPENDENCIES
# =========================================================

def get_incident_repository(
    session: DbSession,
) -> IncidentRepository:
    return (
        SqlAlchemyIncidentRepository(
            session
        )
    )


IncidentRepositoryDependency = (
    Annotated[
        IncidentRepository,
        Depends(
            get_incident_repository
        ),
    ]
)


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


IncidentServiceDependency = (
    Annotated[
        IncidentService,
        Depends(
            get_incident_service
        ),
    ]
)


@lru_cache(
    maxsize=1
)
def get_incident_http_client(
) -> httpx.Client:
    """
    Construct the process-wide Incident Service HTTP client.

    Reusing one client preserves connection pooling across
    requests while the Core Backend process is running.
    """

    return (
        httpx.Client(
            timeout=(
                settings
                .incident_service_timeout_seconds
            ),
        )
    )

@lru_cache(
    maxsize=1
)
def get_incident_circuit_breaker(
) -> CircuitBreaker:
    """
    Construct the process-local Incident Service circuit.

    HttpIncidentGateway objects are created through FastAPI's
    dependency graph, but all of them must share this breaker
    state across requests in the current Backend process.
    """

    return CircuitBreaker(
        failure_threshold=(
            settings
            .incident_service_circuit_failure_threshold
        ),
        recovery_seconds=(
            settings
            .incident_service_circuit_recovery_seconds
        ),
    )


def get_incident_gateway(
    incident_service: (
        IncidentServiceDependency
    ),
) -> IncidentGateway:
    if (
        settings
        .incident_gateway_mode
        == "http"
    ):
        return (
            HttpIncidentGateway(
                client=(
                    get_incident_http_client()
                ),
                incident_service_url=(
                    settings
                    .incident_service_url
                ),
                service_token_provider=(
                    get_service_token_provider()
                ),
                incident_service_audience=(
                    settings
                    .incident_service_audience
                ),
                read_max_attempts=(
                    settings
                    .incident_service_read_max_attempts
                ),
                read_backoff_seconds=(
                    settings
                    .incident_service_read_backoff_seconds
                ),
                circuit_breaker=(
                    get_incident_circuit_breaker()
                ),
                metrics=(
                    operational_metrics
                    if settings.metrics_enabled
                    else None
                ),
            )
        )

    return (
        LocalIncidentGateway(
            incident_service
        )
    )


IncidentGatewayDependency = (
    Annotated[
        IncidentGateway,
        Depends(
            get_incident_gateway
        ),
    ]
)


# =========================================================
# LOGIN ABUSE PROTECTION
# =========================================================

@lru_cache(
    maxsize=1
)
def get_login_throttle(
) -> LoginThrottle:
    """
    Construct the process-local login throttle.

    One shared limiter instance must survive across requests.
    Otherwise each request would begin with an empty throttle
    state and abuse protection would be ineffective.
    """

    return (
        InMemoryLoginThrottle(
            secret_key=(
                settings
                .auth_throttle_secret_key
                .get_secret_value()
            ),
            ip_max_attempts=(
                settings
                .login_ip_max_attempts
            ),
            ip_window_seconds=(
                settings
                .login_ip_window_seconds
            ),
            account_max_failures=(
                settings
                .login_account_max_failures
            ),
            account_window_seconds=(
                settings
                .login_account_window_seconds
            ),
        )
    )


LoginThrottleDependency = (
    Annotated[
        LoginThrottle,
        Depends(
            get_login_throttle
        ),
    ]
)


# =========================================================
# PASSWORD RESET ABUSE PROTECTION
# =========================================================

@lru_cache(
    maxsize=1
)
def get_password_reset_throttle(
) -> PasswordResetThrottle:
    """
    Construct the process-local password-reset throttle.

    Password-reset requests are constrained independently by
    both:

        source IP
        normalized account identifier

    The shared process-local instance preserves limiter state
    between requests.
    """

    return (
        InMemoryPasswordResetThrottle(
            secret_key=(
                settings
                .auth_throttle_secret_key
                .get_secret_value()
            ),
            ip_max_requests=(
                settings
                .password_reset_ip_max_requests
            ),
            ip_window_seconds=(
                settings
                .password_reset_ip_window_seconds
            ),
            account_max_requests=(
                settings
                .password_reset_account_max_requests
            ),
            account_window_seconds=(
                settings
                .password_reset_account_window_seconds
            ),
        )
    )


PasswordResetThrottleDependency = (
    Annotated[
        PasswordResetThrottle,
        Depends(
            get_password_reset_throttle
        ),
    ]
)


# =========================================================
# AUTH SESSION REPOSITORY
# =========================================================

def get_auth_session_repository(
    session: DbSession,
) -> AuthSessionRepository:
    return (
        SqlAlchemyAuthSessionRepository(
            session
        )
    )


AuthSessionRepositoryDependency = (
    Annotated[
        AuthSessionRepository,
        Depends(
            get_auth_session_repository
        ),
    ]
)


# =========================================================
# PASSWORD RESET TOKEN REPOSITORY
# =========================================================

def get_password_reset_token_repository(
    session: DbSession,
) -> PasswordResetTokenRepository:
    return (
        SqlAlchemyPasswordResetTokenRepository(
            session
        )
    )


PasswordResetTokenRepositoryDependency = (
    Annotated[
        PasswordResetTokenRepository,
        Depends(
            get_password_reset_token_repository
        ),
    ]
)


# =========================================================
# PASSWORD RESET SERVICE
# =========================================================

def get_password_reset_service(
    db: DbSession,
    password_reset_repository: (
        PasswordResetTokenRepositoryDependency
    ),
    auth_session_repository: (
        AuthSessionRepositoryDependency
    ),
) -> PasswordResetService:
    user_repository = (
        SqlAlchemyUserRepository(
            db
        )
    )

    return (
        PasswordResetService(
            user_repository=(
                user_repository
            ),
            password_reset_repository=(
                password_reset_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )


PasswordResetServiceDependency = (
    Annotated[
        PasswordResetService,
        Depends(
            get_password_reset_service
        ),
    ]
)


# =========================================================
# AUTHENTICATION SERVICE
# =========================================================

def get_authentication_service(
    db: DbSession,
    auth_session_repository: (
        AuthSessionRepositoryDependency
    ),
) -> AuthenticationService:
    user_repository = (
        SqlAlchemyUserRepository(
            db
        )
    )

    return (
        AuthenticationService(
            repository=(
                user_repository
            ),
            auth_session_repository=(
                auth_session_repository
            ),
        )
    )


# =========================================================
# CURRENT USER
# =========================================================

def get_current_user(
    request: Request,
    token: Annotated[
        str | None,
        Depends(
            oauth2_scheme
        ),
    ],
    authentication_service: Annotated[
        AuthenticationService,
        Depends(
            get_authentication_service
        ),
    ],
) -> User:
    """
    Resolve a bearer access JWT into the active application
    user represented by that credential.

    Missing and invalid bearer credentials intentionally
    share the same public HTTP contract.

    Access-token failures are recorded as security events
    without ever logging the bearer credential itself.
    """

    credentials_exception = (
        HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                ACCESS_CREDENTIALS_INVALID_MESSAGE
            ),
            headers=(
                auth_error_headers(
                    AuthErrorCode
                    .ACCESS_CREDENTIALS_INVALID,
                    additional_headers={
                        "WWW-Authenticate": (
                            "Bearer"
                        ),
                    },
                )
            ),
        )
    )

    if not token:
        security_event_logger.emit(
            event=(
                "auth.access_token.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "missing_access_token"
            ),
        )

        raise (
            credentials_exception
        )

    try:
        return (
            authentication_service
            .resolve_access_token(
                token
            )
        )

    except AuthenticationError as exc:
        security_event_logger.emit(
            event=(
                "auth.access_token.failed"
            ),
            outcome="failure",
            level=logging.WARNING,
            request=request,
            reason=(
                "invalid_access_token"
            ),
        )

        raise (
            credentials_exception
        ) from exc


CurrentUser = (
    Annotated[
        User,
        Depends(
            get_current_user
        ),
    ]
)


# =========================================================
# PASSWORD RESET LINK BUILDER
# =========================================================

@lru_cache(
    maxsize=1
)
def get_password_reset_link_builder(
) -> PasswordResetLinkBuilder:
    """
    Construct the application password-reset link builder.

    The builder owns creation of the frontend recovery URL.
    The raw recovery credential is handed to it only while
    constructing the outbound recovery message.
    """

    return (
        PasswordResetLinkBuilder(
            reset_url=(
                settings
                .password_reset_url
            ),
        )
    )


PasswordResetLinkBuilderDependency = (
    Annotated[
        PasswordResetLinkBuilder,
        Depends(
            get_password_reset_link_builder
        ),
    ]
)


# =========================================================
# AWS SES CLIENT
# =========================================================

@lru_cache(
    maxsize=1
)
def get_ses_client(
) -> SesClient:
    """
    Construct the process-wide AWS SES v2 client.

    boto3 resolves credentials through its normal AWS
    credential provider chain.

    AWS credentials must never be embedded in application
    source code.

    Conservative network timeouts keep an unavailable email
    provider from holding password-reset requests open for an
    excessive amount of time.
    """

    try:
        client = (
            boto3.client(
                "sesv2",
                region_name=(
                    settings
                    .aws_region
                ),
                config=(
                    Config(
                        connect_timeout=3,
                        read_timeout=5,
                        retries={
                            "mode": (
                                "standard"
                            ),
                            "total_max_attempts": (
                                3
                            ),
                        },
                    )
                ),
            )
        )

    except BotoCoreError as exc:
        raise (
            PasswordResetDeliveryError(
                "Password reset email "
                "delivery is unavailable."
            )
        ) from exc

    return (
        cast(
            SesClient,
            client,
        )
    )


SesClientDependency = (
    Annotated[
        SesClient,
        Depends(
            get_ses_client
        ),
    ]
)


# =========================================================
# PASSWORD RESET DELIVERY
# =========================================================

def get_password_reset_delivery(
    ses_client: SesClientDependency,
) -> PasswordResetDelivery:
    """
    Construct the production password-reset delivery adapter.

    This is intentionally the single delivery factory in the
    dependency graph.
    """

    return (
        SesPasswordResetDelivery(
            client=(
                ses_client
            ),
            sender_email=(
                settings
                .ses_from_email
            ),
            configuration_set_name=(
                settings
                .ses_configuration_set_name
            ),
        )
    )


PasswordResetDeliveryDependency = (
    Annotated[
        PasswordResetDelivery,
        Depends(
            get_password_reset_delivery
        ),
    ]
)


# =========================================================
# PASSWORD RESET DELIVERY COORDINATOR
# =========================================================

def get_password_reset_delivery_coordinator(
    link_builder: (
        PasswordResetLinkBuilderDependency
    ),
    delivery: (
        PasswordResetDeliveryDependency
    ),
) -> PasswordResetDeliveryCoordinator:
    """
    Combine recovery-link construction with the configured
    outbound delivery adapter.

    Dependency chain:

        PasswordResetDeliveryCoordinator
            |
            +-- PasswordResetLinkBuilder
            |
            +-- SesPasswordResetDelivery
                    |
                    +-- boto3 SES v2 client
    """

    return (
        PasswordResetDeliveryCoordinator(
            link_builder=(
                link_builder
            ),
            delivery=(
                delivery
            ),
        )
    )


PasswordResetDeliveryCoordinatorDependency = (
    Annotated[
        PasswordResetDeliveryCoordinator,
        Depends(
            get_password_reset_delivery_coordinator
        ),
    ]
)
