from app.domain.authorization import (
    Permission,
    ROLE_PERMISSIONS,
)
from app.domain.user import User


class AuthorizationError(Exception):
    pass


class PermissionDeniedError(
    AuthorizationError
):
    pass


class AuthorizationService:
    def has_permission(
        self,
        user: User,
        permission: Permission,
    ) -> bool:
        role_permissions = ROLE_PERMISSIONS.get(
            user.role,
            frozenset(),
        )

        return permission in role_permissions

    def require_permission(
        self,
        user: User,
        permission: Permission,
    ) -> None:
        if not self.has_permission(
            user,
            permission,
        ):
            raise PermissionDeniedError(
                (
                    f"User role '{user.role.value}' "
                    f"does not have permission "
                    f"'{permission.value}'."
                )
            )