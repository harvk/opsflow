from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from fastapi.testclient import (
    TestClient,
)

from sqlalchemy.orm import (
    Session,
)

from app.core.config import (
    settings,
)

from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_reauthentication_token,
    decode_access_token,
    decode_reauthentication_token,
    hash_password,
)

from app.repositories.sqlalchemy_auth_session_repository import (
    SqlAlchemyAuthSessionRepository,
)

from app.repositories.sqlalchemy_user_repository import (
    SqlAlchemyUserRepository,
)

from app.services.authentication_service import (
    AuthenticationService,
    ReauthenticationError,
)

from app.services.user_service import (
    UserService,
)


TEST_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# HELPERS
# =========================================================


def build_authentication_service(
    db_session: Session,
) -> tuple[
    AuthenticationService,
    SqlAlchemyUserRepository,
]:
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    session_repository = (
        SqlAlchemyAuthSessionRepository(
            db_session
        )
    )

    authentication_service = (
        AuthenticationService(
            repository=(
                user_repository
            ),
            auth_session_repository=(
                session_repository
            ),
        )
    )

    return (
        authentication_service,
        user_repository,
    )


def create_test_user(
    user_repository: (
        SqlAlchemyUserRepository
    ),
):
    service = (
        UserService(
            user_repository
        )
    )

    return service.create_user(
        email=(
            f"reauth-"
            f"{uuid4().hex}"
            "@example.com"
        ),
        full_name=(
            "Reauthentication Test User"
        ),
        password=(
            TEST_PASSWORD
        ),
    )


# =========================================================
# JWT TESTS
# =========================================================


def test_reauthentication_token_round_trip(
) -> None:
    user_id = (
        uuid4()
    )

    credential_hash = (
        hash_password(
            TEST_PASSWORD
        )
    )

    token = (
        create_reauthentication_token(
            user_id,
            credential_hash=(
                credential_hash
            ),
        )
    )

    claims = (
        decode_reauthentication_token(
            token
        )
    )

    assert (
        claims.user_id
        == user_id
    )

    assert (
        claims.credential_fingerprint
    )


def test_expired_reauthentication_token_is_rejected(
) -> None:
    token = (
        create_reauthentication_token(
            uuid4(),
            credential_hash=(
                hash_password(
                    TEST_PASSWORD
                )
            ),
            expires_delta=(
                timedelta(
                    seconds=-1
                )
            ),
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_reauthentication_token(
            token
        )


def test_access_token_cannot_be_used_as_reauthentication_token(
) -> None:
    access_token = (
        create_access_token(
            uuid4()
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_reauthentication_token(
            access_token
        )


def test_reauthentication_token_cannot_be_used_as_access_token(
) -> None:
    reauth_token = (
        create_reauthentication_token(
            uuid4(),
            credential_hash=(
                hash_password(
                    TEST_PASSWORD
                )
            ),
        )
    )

    with pytest.raises(
        TokenValidationError
    ):
        decode_access_token(
            reauth_token
        )


# =========================================================
# SERVICE TESTS
# =========================================================


def test_correct_current_password_issues_reauth_token(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    result = (
        authentication_service
        .reauthenticate(
            user,
            password=(
                TEST_PASSWORD
            ),
        )
    )

    claims = (
        decode_reauthentication_token(
            result.reauth_token
        )
    )

    assert (
        claims.user_id
        == user.id
    )

    assert (
        result.expires_in_seconds
        == (
            settings
            .reauth_token_expire_minutes
            * 60
        )
    )


def test_wrong_current_password_is_rejected(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    with pytest.raises(
        ReauthenticationError
    ):
        authentication_service.reauthenticate(
            user,
            password=(
                "DefinitelyWrongPassword!"
            ),
        )


def test_reauthentication_token_resolves_user(
    db_session: Session,
) -> None:
    (
        authentication_service,
        user_repository,
    ) = build_authentication_service(
        db_session
    )

    user = create_test_user(
        user_repository
    )

    result = (
        authentication_service
        .reauthenticate(
            user,
            password=(
                TEST_PASSWORD
            ),
        )
    )

    resolved_user = (
        authentication_service
        .resolve_reauthentication_token(
            result.reauth_token
        )
    )

    assert (
        resolved_user.id
        == user.id
    )


# =========================================================
# API TESTS
# =========================================================


def test_reauthenticate_requires_access_token(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/reauthenticate",
        json={
            "password": (
                TEST_PASSWORD
            )
        },
    )

    assert (
        response.status_code
        == 401
    )


def test_reauthenticate_endpoint_returns_short_lived_proof(
    client: TestClient,
    db_session: Session,
) -> None:
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = create_test_user(
        user_repository
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    response = client.post(
        "/api/v1/auth/reauthenticate",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "password": (
                TEST_PASSWORD
            )
        },
    )

    assert (
        response.status_code
        == 200
    )

    body = (
        response.json()
    )

    assert (
        body["token_type"]
        == "reauth"
    )

    assert (
        body[
            "expires_in_seconds"
        ]
        == (
            settings
            .reauth_token_expire_minutes
            * 60
        )
    )

    claims = (
        decode_reauthentication_token(
            body[
                "reauth_token"
            ]
        )
    )

    assert (
        claims.user_id
        == user.id
    )


def test_reauthenticate_endpoint_rejects_wrong_password(
    client: TestClient,
    db_session: Session,
) -> None:
    user_repository = (
        SqlAlchemyUserRepository(
            db_session
        )
    )

    user = create_test_user(
        user_repository
    )

    access_token = (
        create_access_token(
            user.id
        )
    )

    response = client.post(
        "/api/v1/auth/reauthenticate",
        headers={
            "Authorization": (
                f"Bearer {access_token}"
            )
        },
        json={
            "password": (
                "DefinitelyWrongPassword!"
            )
        },
    )

    assert (
        response.status_code
        == 401
    )

    assert response.json() == {
        "detail": (
            "Reauthentication failed."
        )
    }