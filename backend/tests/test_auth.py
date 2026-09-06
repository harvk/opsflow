from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.domain.user import UserRole
from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)
from app.services.user_service import (
    UserService,
)

from app.core.config import settings


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
    
    
def test_login_sets_httponly_refresh_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "admin@example.com"
            ),
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert response.status_code == 200

    set_cookie = (
        response.headers[
            "set-cookie"
        ]
        .lower()
    )

    assert (
        settings
        .refresh_cookie_name
        .lower()
        in set_cookie
    )

    assert "httponly" in set_cookie

    assert (
        "samesite=lax"
        in set_cookie
    )

    assert (
        f"path={settings.refresh_cookie_path}".lower()
        in set_cookie
    )


def test_refresh_returns_new_access_token(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    original_access_token = (
        login_response.json()[
            "access_token"
        ]
    )

    csrf_token = client.cookies.get(
        "opsflow_csrf"
    )

    assert csrf_token is not None

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        headers={
            "X-CSRF-Token": (
                csrf_token
            ),
        },
    )

    assert (
        refresh_response.status_code
        == 200
    ), refresh_response.text

    body = (
        refresh_response.json()
    )

    assert body["access_token"]

    assert (
        body["access_token"]
        != original_access_token
    )

    assert (
        body["token_type"]
        == "bearer"
    )


def test_refresh_requires_refresh_cookie(
    client: TestClient,
) -> None:
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/refresh"
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Could not refresh credentials."
        )
    }


def test_access_token_is_rejected_as_refresh_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    client.cookies.set(
        settings.refresh_cookie_name,
        access_token,
    )

    response = client.post(
        "/api/v1/auth/refresh"
    )

    assert response.status_code == 401


def test_refresh_token_is_rejected_as_bearer_access_token(
    client: TestClient,
    db_session: Session,
) -> None:
    user = create_test_user(
        db_session
    )

    refresh_token = (
        create_refresh_token(
            user.id
        )
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Authorization": (
                f"Bearer {refresh_token}"
            )
        },
    )

    assert response.status_code == 401


def test_logout_clears_refresh_cookie(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    csrf_token = client.cookies.get(
        "opsflow_csrf"
    )

    assert csrf_token is not None

    logout_response = client.post(
        "/api/v1/auth/logout",
        headers={
            "X-CSRF-Token": (
                csrf_token
            ),
        },
    )

    assert (
        logout_response.status_code
        == 204
    ), logout_response.text

    assert (
        client.cookies.get(
            "opsflow_refresh_token"
        )
        is None
    )

    assert (
        client.cookies.get(
            "opsflow_csrf"
        )
        is None
    )
    
def test_refresh_requires_csrf_header(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    assert (
        client.cookies.get(
            "opsflow_csrf"
        )
        is not None
    )

    response = client.post(
        "/api/v1/auth/refresh"
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }
    
def test_refresh_rejects_mismatched_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    response = client.post(
        "/api/v1/auth/refresh",
        headers={
            "X-CSRF-Token": (
                "definitely-not-"
                "the-correct-token"
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }
    
def test_refresh_accepts_valid_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    csrf_token = client.cookies.get(
        "opsflow_csrf"
    )

    assert csrf_token is not None

    response = client.post(
        "/api/v1/auth/refresh",
        headers={
            "X-CSRF-Token": (
                csrf_token
            ),
        },
    )

    assert (
        response.status_code
        == 200
    ), response.text

    body = response.json()

    assert body["access_token"]

    assert (
        body["token_type"]
        == "bearer"
    )
    
def test_logout_requires_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    response = client.post(
        "/api/v1/auth/logout"
    )

    assert (
        response.status_code
        == 403
    )

    # Invalid CSRF must NOT force the user out.
    assert (
        client.cookies.get(
            "opsflow_refresh_token"
        )
        is not None
    )

    assert (
        client.cookies.get(
            "opsflow_csrf"
        )
        is not None
    )
    
def test_logout_with_valid_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    csrf_token = client.cookies.get(
        "opsflow_csrf"
    )

    assert csrf_token is not None

    response = client.post(
        "/api/v1/auth/logout",
        headers={
            "X-CSRF-Token": (
                csrf_token
            ),
        },
    )

    assert (
        response.status_code
        == 204
    ), response.text

    assert (
        client.cookies.get(
            "opsflow_refresh_token"
        )
        is None
    )

    assert (
        client.cookies.get(
            "opsflow_csrf"
        )
        is None
    )
    
def test_cross_site_refresh_is_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "admin@example.com",
            "password": (
                "VerySecurePassword123!"
            ),
        },
    )

    assert (
        login_response.status_code
        == 200
    )

    csrf_token = client.cookies.get(
        "opsflow_csrf"
    )

    assert csrf_token is not None

    response = client.post(
        "/api/v1/auth/refresh",
        headers={
            "Origin": (
                "https://evil.example"
            ),
            "Sec-Fetch-Site": (
                "cross-site"
            ),
            "X-CSRF-Token": (
                csrf_token
            ),
        },
    )

    assert (
        response.status_code
        == 403
    )