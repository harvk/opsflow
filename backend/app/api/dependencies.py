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

from botocore.config import (
    Config,
)

from botocore.exceptions import (
    BotoCoreError,
)

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from fastapi.security import (
    OAuth2PasswordBearer,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from app.core.login_throttle import (
    InMemoryLoginThrottle,
    LoginThrottle,
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

from app.db.session import (
    get_db_session,
)

from app.domain.authorization import (
    Permission,
)

from app.domain.user import (
    User,
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
# OAUTH2
# =========================================================


oauth2_scheme = (
    OAuth2PasswordBearer(
        tokenUrl=(
            "api/v1/auth/token"
        )
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
    service_repository: (
        ServiceRepositoryDependency
    ),
) -> IncidentService:
    return (
        IncidentService(
            incident_repository=(
                incident_repository
            ),
            service_repository=(
                service_repository
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

    lru_cache gives the application one shared throttle
    instance rather than creating a new empty limiter for
    every request.
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

    The same limiter instance must survive across requests;
    otherwise every request would receive fresh, empty
    throttle state.

    Password-reset requests count immediately against both:

        source IP
        normalized account identifier
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
# PASSWORD RESET PERSISTENCE
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
# AWS SES
# =========================================================


@lru_cache(
    maxsize=1
)
def get_ses_client(
) -> SesClient:
    """
    Construct the shared AWS SES client.

    boto3 uses the normal AWS credential provider chain.

    AWS credentials are therefore not embedded in application
    source code.

    A shared client is appropriate because boto3 clients are
    designed to be reused between requests.

    Relatively short connection/read timeouts prevent an SES
    outage from holding a password-reset request open for an
    excessive amount of time.
    """

    try:
        client = (
            boto3.client(
                "ses",
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

    return cast(
        SesClient,
        client,
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


@lru_cache(
    maxsize=1
)
def get_password_reset_link_builder(
) -> PasswordResetLinkBuilder:
    """
    Construct the frontend password-reset link builder from
    application configuration.

    PasswordResetLinkBuilder validates the configured URL
    when this dependency is first created.
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


def get_password_reset_delivery(
    ses_client: SesClientDependency,
) -> PasswordResetDelivery:
    """
    Construct the password-reset delivery adapter backed by
    AWS SES.

    The boto3 SES client itself is cached separately. This
    adapter is intentionally lightweight and therefore does
    not need its own lru_cache.
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


def get_password_reset_delivery_coordinator(
    link_builder: (
        PasswordResetLinkBuilderDependency
    ),
    delivery: (
        PasswordResetDeliveryDependency
    ),
) -> PasswordResetDeliveryCoordinator:
    """
    Compose password-reset link generation with the currently
    configured delivery infrastructure.
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


# =========================================================
# AUTHENTICATION DEPENDENCIES
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


def get_current_user(
    request: Request,
    token: Annotated[
        str,
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
    Resolve the bearer access JWT into an active user.

    Failed access-token validation is recorded as a security
    event, but the token itself is never logged.
    """

    credentials_exception = (
        HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Could not validate "
                "credentials."
            ),
            headers={
                "WWW-Authenticate": (
                    "Bearer"
                ),
                "Cache-Control": (
                    "no-store"
                ),
                "Pragma": (
                    "no-cache"
                ),
            },
        )
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


CurrentUser = Annotated[
    User,
    Depends(
        get_current_user
    ),
]