from typing import Annotated

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.domain.authorization import Permission

from app.services.authorization_service import (
    AuthorizationService,
    PermissionDeniedError
)

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

from app.domain.user import User

from app.repositories.sqlalchemy_user_repository import SqlAlchemyUserRepository

from app.services.authentication_service import (
    AuthenticationError,
    AuthenticationService
)


authorization_service = AuthorizationService()


DbSession = Annotated[
    Session,
    Depends(get_db_session),
]


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/token"
)


# ---------------------------------------------------------
# Permissions
# ---------------------------------------------------------

def require_permission(
    permission: Permission,
) -> Callable[..., User]:
    def permission_dependency(
        current_user: CurrentUser,
    ) -> User:
        try:
            authorization_service.require_permission(
                current_user,
                permission,
            )
        except PermissionDeniedError as exc:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "You do not have permission "
                    "to perform this action."
                ),
            ) from exc

        return current_user

    return permission_dependency


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


# ---------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------

def get_authentication_service(
    db: Annotated[Session, Depends(get_db_session)],
) -> AuthenticationService:
    repository = SqlAlchemyUserRepository(
        db
    )

    return AuthenticationService(
        repository
    )


def get_current_user(
    token: Annotated[
        str,
        Depends(oauth2_scheme),
    ],
    authentication_service: Annotated[
        AuthenticationService,
        Depends(get_authentication_service),
    ],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={
            "WWW-Authenticate": "Bearer"
        },
    )

    try:
        return authentication_service.resolve_access_token(
            token
        )
    except AuthenticationError as exc:
        raise credentials_exception from exc
    except ValueError as exc:
        raise credentials_exception from exc
    
CurrentUser = Annotated[
    User,
    Depends(get_current_user),
]