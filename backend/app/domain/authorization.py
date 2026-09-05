from enum import Enum

from app.domain.user import UserRole


class Permission(str, Enum):
    SERVICE_READ = "service:read"
    SERVICE_CREATE = "service:create"
    SERVICE_UPDATE = "service:update"
    SERVICE_DELETE = "service:delete"

    SERVICE_DEPENDENCY_READ = (
        "service_dependency:read"
    )
    SERVICE_DEPENDENCY_WRITE = (
        "service_dependency:write"
    )

    INCIDENT_READ = "incident:read"
    INCIDENT_CREATE = "incident:create"
    INCIDENT_UPDATE = "incident:update"
    INCIDENT_DELETE = "incident:delete"


ROLE_PERMISSIONS: dict[
    UserRole,
    frozenset[Permission],
] = {
    UserRole.VIEWER: frozenset(
        {
            Permission.SERVICE_READ,
            Permission.SERVICE_DEPENDENCY_READ,
            Permission.INCIDENT_READ,
        }
    ),

    UserRole.OPERATOR: frozenset(
        {
            Permission.SERVICE_READ,
            Permission.SERVICE_CREATE,
            Permission.SERVICE_UPDATE,

            Permission.SERVICE_DEPENDENCY_READ,
            Permission.SERVICE_DEPENDENCY_WRITE,

            Permission.INCIDENT_READ,
            Permission.INCIDENT_CREATE,
            Permission.INCIDENT_UPDATE,
        }
    ),

    UserRole.ADMIN: frozenset(
        {
            Permission.SERVICE_READ,
            Permission.SERVICE_CREATE,
            Permission.SERVICE_UPDATE,
            Permission.SERVICE_DELETE,

            Permission.SERVICE_DEPENDENCY_READ,
            Permission.SERVICE_DEPENDENCY_WRITE,

            Permission.INCIDENT_READ,
            Permission.INCIDENT_CREATE,
            Permission.INCIDENT_UPDATE,
            Permission.INCIDENT_DELETE,
        }
    ),
}