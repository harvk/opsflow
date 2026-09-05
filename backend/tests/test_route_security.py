from fastapi.testclient import TestClient


def test_services_require_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/services"
    )

    assert response.status_code == 401


def test_incidents_require_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/incidents"
    )

    assert response.status_code == 401


def test_health_remains_public(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/health"
    )

    assert response.status_code == 200


def test_login_endpoint_remains_public(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={
            "username": (
                "does-not-exist@example.com"
            ),
            "password": (
                "DefinitelyWrongPassword!"
            ),
        },
    )

    # Authentication fails because credentials
    # are bad, NOT because the route itself
    # requires an existing bearer token.
    assert response.status_code == 401

    assert response.json() == {
        "detail": (
            "Incorrect email or password."
        )
    }