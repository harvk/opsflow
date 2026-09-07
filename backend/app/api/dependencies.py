from collections.abc import (
    Callable,
)
from functools import (
    lru_cache,
)
from typing import (
    Annotated,
)

from fastapi import (
    Depends,
    HTTPException,
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

from app.db.session import (
    get_db_session,
)

from app.domain.authorization import (
    Permission,
)

from app.domain.user import (
    User,
)

from app.repositories.auth_session_repository import (
    AuthSessionRepository,
)

from app.repositories.incident_repository import (
    IncidentRepository,
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
    return ServiceService(
        repository
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
    return IncidentService(
        incident_repository=(
            incident_repository
        ),
        service_repository=(
            service_repository
        ),
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

    return InMemoryLoginThrottle(
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


LoginThrottleDependency = (
    Annotated[
        LoginThrottle,
        Depends(
            get_login_throttle
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


AuthSessionRepositoryDependency = Annotated[
    AuthSessionRepository,
    Depends(
        get_auth_session_repository
    ),
]


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

    return AuthenticationService(
        repository=(
            user_repository
        ),
        auth_session_repository=(
            auth_session_repository
        ),
    )


def get_current_user(
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
                )
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
        raise (
            credentials_exception
        ) from exc


CurrentUser = Annotated[
    User,
    Depends(
        get_current_user
    ),
]