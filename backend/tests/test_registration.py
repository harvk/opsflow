from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

REGISTER_URL = "/api/v1/auth/register"
VALID_PASSWORD = "VerySecurePassword123!"


def test_registration_creates_least_privilege_account(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        REGISTER_URL,
        json={
            "email": "New.User@Example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 201, response.text

    body = response.json()

    assert body["email"] == "new.user@example.com"
    assert body["full_name"] == "new.user"
    assert body["role"] == UserRole.VIEWER.value
    assert body["is_active"] is True
    assert body["id"] is not None

    repository = SqlAlchemyUserRepository(db_session)
    auth_record = repository.get_auth_record_by_email(
        "new.user@example.com"
    )

    assert auth_record is not None
    assert auth_record.hashed_password != VALID_PASSWORD
    assert verify_password(
        VALID_PASSWORD,
        auth_record.hashed_password,
    )


def test_registration_rejects_duplicate_email(
    client: TestClient,
) -> None:
    first_response = client.post(
        REGISTER_URL,
        json={
            "email": "duplicate@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert first_response.status_code == 201, first_response.text

    duplicate_response = client.post(
        REGISTER_URL,
        json={
            "email": "DUPLICATE@example.com",
            "password": VALID_PASSWORD,
        },
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "detail": "An account with that email already exists."
    }


def test_registration_enforces_shared_password_policy(
    client: TestClient,
) -> None:
    response = client.post(
        REGISTER_URL,
        json={
            "email": "short-password@example.com",
            "password": "too-short",
        },
    )

    assert response.status_code == 422


def test_registration_rejects_invalid_email(
    client: TestClient,
) -> None:
    response = client.post(
        REGISTER_URL,
        json={
            "email": "not-an-email",
            "password": VALID_PASSWORD,
        },
    )

    assert response.status_code == 422
