from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
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
from app.api.dependencies import (
    get_login_throttle,
)

from app.core.login_throttle import (
    InMemoryLoginThrottle,
)

from app.main import app


# =========================================================
# AUTHENTICATION TEST CONSTANTS
# =========================================================


AUTH_TOKEN_PATH = (
    f"{settings.api_v1_prefix}/auth/token"
)

AUTH_REFRESH_PATH = (
    f"{settings.api_v1_prefix}/auth/refresh"
)

AUTH_LOGOUT_PATH = (
    f"{settings.api_v1_prefix}/auth/logout"
)

AUTH_ME_PATH = (
    f"{settings.api_v1_prefix}/auth/me"
)


DEFAULT_EMAIL = (
    "admin@example.com"
)

DEFAULT_PASSWORD = (
    "VerySecurePassword123!"
)


# =========================================================
# TEST HELPERS
# =========================================================


def create_test_user(
    db_session: Session,
    *,
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
):
    """
    Create the standard administrator used throughout the
    authentication route tests.

    The user is written through the real SQLAlchemy-backed
    user repository and participates in the transaction
    controlled by the db_session fixture.
    """

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


def login_test_user(
    client: TestClient,
    db_session: Session,
):
    """
    Create and authenticate the standard test user.

    Returning the login response lets individual tests
    inspect:

        JSON access-token behavior
        Set-Cookie behavior
        browser cookie state
    """

    create_test_user(
        db_session
    )

    response = client.post(
        AUTH_TOKEN_PATH,
        data={
            "username": DEFAULT_EMAIL,
            "password": DEFAULT_PASSWORD,
        },
    )

    assert (
        response.status_code
        == 200
    ), response.text

    return response


def get_csrf_token(
    client: TestClient,
) -> str:
    """
    Retrieve the CSRF cookie created during authentication.

    Unlike the HttpOnly refresh credential, this cookie is
    intentionally readable by browser JavaScript so React
    can copy its value into the configured CSRF header.
    """

    csrf_token = client.cookies.get(
        settings.csrf_cookie_name
    )

    assert csrf_token is not None

    return csrf_token


def csrf_headers(
    csrf_token: str,
) -> dict[str, str]:
    """
    Build the same CSRF-header shape expected by the
    authentication routes.
    """

    return {
        settings.csrf_header_name: (
            csrf_token
        )
    }


def tamper_token(
    token: str,
) -> str:
    """
    Change the token without destroying its basic string
    shape.

    This lets us test cryptographic validation rather than
    merely testing an obviously missing value.
    """

    assert token

    replacement = (
        "A"
        if token[0] != "A"
        else "B"
    )

    return (
        replacement
        + token[1:]
    )


# =========================================================
# LOGIN
# =========================================================


def test_login_returns_access_token(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    response = client.post(
        AUTH_TOKEN_PATH,
        data={
            "username": DEFAULT_EMAIL,
            "password": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"]

    assert (
        body["token_type"]
        == "bearer"
    )

    # Refresh and CSRF credentials belong in cookies,
    # not in the JSON response exposed to React.
    assert (
        "refresh_token"
        not in body
    )

    assert (
        "csrf_token"
        not in body
    )


def test_login_sets_authentication_cookies(
    client: TestClient,
    db_session: Session,
) -> None:
    response = login_test_user(
        client,
        db_session,
    )

    refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    csrf_cookie = (
        client.cookies.get(
            settings.csrf_cookie_name
        )
    )

    assert refresh_cookie is not None
    assert csrf_cookie is not None

    # Find the Set-Cookie header specifically responsible
    # for the JavaScript-readable CSRF cookie.
    set_cookie_headers = (
        response.headers.get_list(
            "set-cookie"
        )
    )

    csrf_cookie_header = next(
        header
        for header in set_cookie_headers
        if header.startswith(
            f"{settings.csrf_cookie_name}="
        )
    )

    normalized_header = (
        csrf_cookie_header.lower()
    )

    # The frontend must be able to read the CSRF value.
    assert (
        "httponly"
        not in normalized_header
    )

    # The CSRF cookie is deliberately available throughout
    # the SPA rather than being limited to /api/v1/auth.
    assert (
        "path=/"
        in normalized_header
    )

    assert (
        (
            "samesite="
            f"{settings.refresh_cookie_samesite}"
        )
        in normalized_header
    )

    if settings.is_production:
        assert (
            "secure"
            in normalized_header
        )
    else:
        assert (
            "secure"
            not in normalized_header
        )


def test_login_rejects_wrong_password(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    response = client.post(
        AUTH_TOKEN_PATH,
        data={
            "username": DEFAULT_EMAIL,
            "password": (
                "WrongPassword123!"
            ),
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
        AUTH_TOKEN_PATH,
        data={
            "username": (
                "missing@example.com"
            ),
            "password": (
                "WrongPassword123!"
            ),
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }


# =========================================================
# CURRENT USER
# =========================================================


def test_me_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        AUTH_ME_PATH
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
        AUTH_ME_PATH,
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["id"]
        == str(user.id)
    )

    assert (
        body["email"]
        == DEFAULT_EMAIL
    )

    assert (
        body["role"]
        == UserRole.ADMIN.value
    )

    assert (
        body["is_active"]
        is True
    )

    assert (
        "hashed_password"
        not in body
    )

    assert (
        "password"
        not in body
    )


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
        AUTH_ME_PATH,
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
        AUTH_ME_PATH,
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
            DEFAULT_PASSWORD
        ),
        role=UserRole.VIEWER,
        is_active=False,
    )

    token = create_access_token(
        user.id
    )

    response = client.get(
        AUTH_ME_PATH,
        headers={
            "Authorization": (
                f"Bearer {token}"
            )
        },
    )

    assert response.status_code == 401


# =========================================================
# REFRESH — BASELINE SECURITY
# =========================================================


def test_refresh_requires_refresh_cookie(
    client: TestClient,
) -> None:
    """
    Refresh cannot occur from CSRF proof alone.

    The browser must first possess a valid refresh
    credential.
    """

    response = client.post(
        AUTH_REFRESH_PATH
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Could not refresh credentials."
        )
    }


def test_refresh_requires_csrf_header(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    A browser that possesses the cookies but does not
    deliberately echo its CSRF token into the request
    header must be rejected.
    """

    login_test_user(
        client,
        db_session,
    )

    original_refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    original_csrf_cookie = (
        get_csrf_token(
            client
        )
    )

    response = client.post(
        AUTH_REFRESH_PATH
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    # A CSRF failure must not become a forced-logout
    # primitive.
    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        == original_refresh_cookie
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == original_csrf_cookie
    )


def test_refresh_rejects_mismatched_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    Possessing a CSRF cookie is insufficient when the
    deliberately supplied header does not match it.
    """

    login_test_user(
        client,
        db_session,
    )

    original_refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    original_csrf_cookie = (
        get_csrf_token(
            client
        )
    )

    response = client.post(
        AUTH_REFRESH_PATH,
        headers=csrf_headers(
            "definitely-not-the-correct-token"
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        == original_refresh_cookie
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == original_csrf_cookie
    )


def test_refresh_rejects_tampered_signed_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    This is stronger than a simple cookie/header mismatch.

    The attacker-controlled cookie and header contain the
    SAME value, but that value is a modified version of the
    signed CSRF token.

    Matching attacker-controlled values must therefore
    still fail cryptographic CSRF validation.
    """

    login_test_user(
        client,
        db_session,
    )

    original_refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    original_csrf_token = (
        get_csrf_token(
            client
        )
    )

    tampered_csrf_token = (
        tamper_token(
            original_csrf_token
        )
    )

    # Replace the legitimate CSRF cookie with the tampered
    # value so the cookie and header deliberately match.
    client.cookies.delete(
        settings.csrf_cookie_name
    )

    client.cookies.set(
        settings.csrf_cookie_name,
        tampered_csrf_token,
        path="/",
    )

    response = client.post(
        AUTH_REFRESH_PATH,
        headers=csrf_headers(
            tampered_csrf_token
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    # The refresh credential itself was not invalid, so it
    # must not be destroyed merely because CSRF proof was
    # forged.
    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        == original_refresh_cookie
    )


def test_refresh_accepts_valid_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    The complete valid browser-authentication state must
    still succeed after all negative checks are added.
    """

    login_response = login_test_user(
        client,
        db_session,
    )

    original_access_token = (
        login_response.json()[
            "access_token"
        ]
    )

    csrf_token = (
        get_csrf_token(
            client
        )
    )

    response = client.post(
        AUTH_REFRESH_PATH,
        headers=csrf_headers(
            csrf_token
        ),
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

    # create_access_token() generates a fresh jti for every
    # token, so a successful refresh should not reproduce
    # the previous access credential.
    assert (
        body["access_token"]
        != original_access_token
    )

    # The existing CSRF proof remains stable across a
    # successful refresh.
    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == csrf_token
    )

    # A usable refresh cookie still exists after refresh.
    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is not None
    )


# =========================================================
# LOGOUT — ADVERSARIAL SECURITY
# =========================================================


def test_logout_requires_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    """
    A cross-site request must not be able to terminate a
    legitimate authenticated browser session merely because
    cookies are attached automatically.
    """

    login_test_user(
        client,
        db_session,
    )

    original_refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    original_csrf_cookie = (
        get_csrf_token(
            client
        )
    )

    response = client.post(
        AUTH_LOGOUT_PATH
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    # Failed CSRF validation intentionally preserves the
    # legitimate authentication state.
    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        == original_refresh_cookie
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == original_csrf_cookie
    )


def test_logout_rejects_mismatched_csrf(
    client: TestClient,
    db_session: Session,
) -> None:
    login_test_user(
        client,
        db_session,
    )

    original_refresh_cookie = (
        client.cookies.get(
            settings.refresh_cookie_name
        )
    )

    original_csrf_cookie = (
        get_csrf_token(
            client
        )
    )

    response = client.post(
        AUTH_LOGOUT_PATH,
        headers=csrf_headers(
            "incorrect-csrf-token"
        ),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": (
            "CSRF validation failed."
        )
    }

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        == original_refresh_cookie
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == original_csrf_cookie
    )


def test_logout_with_valid_csrf_clears_auth_cookies(
    client: TestClient,
    db_session: Session,
) -> None:
    login_test_user(
        client,
        db_session,
    )

    csrf_token = (
        get_csrf_token(
            client
        )
    )

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is not None
    )

    response = client.post(
        AUTH_LOGOUT_PATH,
        headers=csrf_headers(
            csrf_token
        ),
    )

    assert (
        response.status_code
        == 204
    ), response.text

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is None
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        is None
    )


def test_logout_without_refresh_cookie_is_idempotent(
    client: TestClient,
) -> None:
    """
    Logout should remain safe to repeat.

    Simulate a stale CSRF cookie belonging to the same host
    used by Starlette's TestClient while no refresh
    credential exists.
    """

    client.cookies.set(
        settings.csrf_cookie_name,
        "stale-csrf-state",
        domain="testserver.local",
        path="/",
    )

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is None
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        == "stale-csrf-state"
    )

    response = client.post(
        AUTH_LOGOUT_PATH
    )

    assert (
        response.status_code
        == 204
    ), response.text

    assert (
        client.cookies.get(
            settings.refresh_cookie_name
        )
        is None
    )

    assert (
        client.cookies.get(
            settings.csrf_cookie_name
        )
        is None
    )
    
def test_login_rate_limits_repeated_account_failures(
    client: TestClient,
    db_session: Session,
) -> None:
    create_test_user(
        db_session
    )

    throttle = (
        InMemoryLoginThrottle(
            secret_key=(
                "integration-test-secret"
            ),
            ip_max_attempts=100,
            ip_window_seconds=60,
            account_max_failures=2,
            account_window_seconds=300,
        )
    )

    app.dependency_overrides[
        get_login_throttle
    ] = lambda: throttle

    try:
        for _ in range(
            2
        ):
            response = client.post(
                "/api/v1/auth/token",
                data={
                    "username": (
                        "admin@example.com"
                    ),
                    "password": (
                        "WrongPassword123!"
                    ),
                },
            )

            assert (
                response.status_code
                == 401
            )

        # Even the correct password cannot be tested
        # repeatedly once the temporary abuse threshold
        # has been reached.
        blocked_response = client.post(
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

        assert (
            blocked_response.status_code
            == 429
        )

        assert (
            blocked_response.json()
            == {
                "detail": (
                    "Too many authentication "
                    "attempts. Please try again later."
                )
            }
        )

    finally:
        app.dependency_overrides.pop(
            get_login_throttle,
            None,
        )


def test_login_rate_limits_source_across_accounts(
    client: TestClient,
) -> None:
    throttle = (
        InMemoryLoginThrottle(
            secret_key=(
                "integration-test-secret"
            ),
            ip_max_attempts=2,
            ip_window_seconds=60,
            account_max_failures=100,
            account_window_seconds=300,
        )
    )

    app.dependency_overrides[
        get_login_throttle
    ] = lambda: throttle

    try:
        first_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": (
                    "first@example.com"
                ),
                "password": (
                    "WrongPassword123!"
                ),
            },
        )

        second_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": (
                    "second@example.com"
                ),
                "password": (
                    "WrongPassword123!"
                ),
            },
        )

        third_response = client.post(
            "/api/v1/auth/token",
            data={
                "username": (
                    "third@example.com"
                ),
                "password": (
                    "WrongPassword123!"
                ),
            },
        )

        assert (
            first_response.status_code
            == 401
        )

        assert (
            second_response.status_code
            == 401
        )

        assert (
            third_response.status_code
            == 429
        )

    finally:
        app.dependency_overrides.pop(
            get_login_throttle,
            None,
        )
        
def test_failed_login_emits_security_event(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    create_test_user(
        db_session
    )

    emitted_events: list[
        dict[str, object]
    ] = []

    from app.api.routes import (
        auth as auth_endpoint,
    )

    def fake_emit(
        **kwargs,
    ) -> None:
        emitted_events.append(
            kwargs
        )

    monkeypatch.setattr(
        auth_endpoint
        .security_event_logger,
        "emit",
        fake_emit,
    )

    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "admin@example.com"
            ),
            "password": (
                "WrongPassword123!"
            ),
        },
    )

    assert (
        response.status_code
        == 401
    )

    matching_events = [
        event
        for event
        in emitted_events
        if event["event"]
        == "auth.login.failed"
    ]

    assert len(
        matching_events
    ) == 1

    event = matching_events[0]

    assert (
        event["outcome"]
        == "failure"
    )

    assert (
        event["reason"]
        == "invalid_credentials"
    )

    assert (
        "password"
        not in event
    )
    
def test_successful_login_emits_security_event(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = create_test_user(
        db_session
    )

    emitted_events: list[
        dict[str, object]
    ] = []

    from app.api.routes import (
        auth as auth_endpoint,
    )

    def fake_emit(
        **kwargs,
    ) -> None:
        emitted_events.append(
            kwargs
        )

    monkeypatch.setattr(
        auth_endpoint
        .security_event_logger,
        "emit",
        fake_emit,
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

    assert (
        response.status_code
        == 200
    )

    success_events = [
        event
        for event
        in emitted_events
        if event["event"]
        == "auth.login.succeeded"
    ]

    assert (
        len(success_events)
        == 1
    )

    assert (
        success_events[0]["user_id"]
        == user.id
    )