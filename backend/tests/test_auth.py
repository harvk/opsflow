from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
)
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import (
    UserService,
)


def create_test_user(
    db_session: Session,
    *,
    email: str = "admin@example.com",
    password: str = "VerySecurePassword123!",
):
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    service = UserService(
        repository
    )

    return service.create_user(
        email=email,
        full_name="Test Administrator",
        password=password,
        role=UserRole.ADMIN,
    )


def test_login_returns_access_token(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_login_rejects_wrong_password(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


def test_login_rejects_unknown_email(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "missing@example.com",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


def test_me_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/auth/me"
    )

    assert response.status_code == 401


def test_me_returns_authenticated_user(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    token = create_access_token(
        user.id
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(user.id)

    assert (
        body["email"]
        == "admin@example.com"
    )

    assert (
        body["role"]
        == UserRole.ADMIN.value
    )

    assert body["is_active"] is True

    assert "hashed_password" not in body
    assert "password" not in body


def test_me_rejects_tampered_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    token = create_access_token(
        user.id
    )

    tampered_token = (
        token[:-1]
        + (
            "a"
            if token[-1] != "a"
            else "b"
        )
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {tampered_token}"
            )
        },
    )

    assert response.status_code == 401


def test_me_rejects_expired_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    token = create_access_token(
        user.id,
        expires_delta=timedelta(
            seconds=-1
        ),
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 401


def test_inactive_user_token_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = repository.add(
        email="inactive@example.com",
        full_name="Inactive User",
        hashed_password=hash_password(
            "VerySecurePassword123!"
        ),
        role=UserRole.VIEWER,
        is_active=False,
    )

    token = create_access_token(
        user.id
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 401