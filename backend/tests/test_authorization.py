from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.domain.authorization import Permission
from app.domain.user import User, UserRole
from app.services.authorization_service import (
    AuthorizationService,
    PermissionDeniedError,
)


def make_user(
    role: UserRole,
) -> User:
    now = datetime.now(timezone.utc)

    return User(
        id=uuid4(),
        email=f"{role.value}@example.com",
        full_name="Authorization Test User",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_viewer_can_read_services() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.VIEWER
    )

    assert service.has_permission(
        user,
        Permission.SERVICE_READ,
    )


def test_viewer_cannot_create_service() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.VIEWER
    )

    assert not service.has_permission(
        user,
        Permission.SERVICE_CREATE,
    )


def test_operator_can_update_incident() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.OPERATOR
    )

    assert service.has_permission(
        user,
        Permission.INCIDENT_UPDATE,
    )


def test_operator_cannot_delete_incident() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.OPERATOR
    )

    assert not service.has_permission(
        user,
        Permission.INCIDENT_DELETE,
    )


def test_admin_can_delete_incident() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.ADMIN
    )

    assert service.has_permission(
        user,
        Permission.INCIDENT_DELETE,
    )


def test_require_permission_raises_when_denied() -> None:
    service = AuthorizationService()

    user = make_user(
        UserRole.VIEWER
    )

    with pytest.raises(
        PermissionDeniedError
    ):
        service.require_permission(
            user,
            Permission.SERVICE_DELETE,
        )