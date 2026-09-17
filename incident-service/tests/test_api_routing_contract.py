from __future__ import annotations

from collections import Counter
from typing import Any, Final

from app.main import app

HTTP_METHODS: Final[frozenset[str]] = frozenset(
    {
        "delete",
        "get",
        "patch",
        "post",
        "put",
    }
)

EXPECTED_INCIDENT_OPERATIONS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("GET", "/api/v1/incidents"),
        (
            "GET",
            "/api/v1/incidents/{incident_id}",
        ),
        ("POST", "/api/v1/incidents"),
        ("PATCH", "/api/v1/incidents/{incident_id}"),
        ("DELETE", "/api/v1/incidents/{incident_id}"),
    }
)

BACKEND_OWNED_PREFIXES: Final[tuple[str, ...]] = (
    "/api/v1/auth",
    "/api/v1/services",
    "/api/v1/password-reset",
)


def _openapi_paths() -> dict[str, Any]:
    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths")

    assert isinstance(paths, dict)

    return paths


def _documented_operations() -> list[tuple[str, str]]:
    operations: list[tuple[str, str]] = []

    for path, path_item in _openapi_paths().items():
        if not isinstance(path_item, dict):
            continue

        for method in HTTP_METHODS:
            if method not in path_item:
                continue

            operations.append((method.upper(), path))

    return operations


def _documented_operation_ids() -> list[str]:
    operation_ids: list[str] = []

    for path_item in _openapi_paths().values():
        if not isinstance(path_item, dict):
            continue

        for method in HTTP_METHODS:
            operation = path_item.get(method)

            if not isinstance(operation, dict):
                continue

            operation_id = operation.get("operationId")

            if isinstance(operation_id, str):
                operation_ids.append(operation_id)

    return operation_ids


def test_incident_service_exposes_incident_routes() -> None:
    operations = set(_documented_operations())

    assert EXPECTED_INCIDENT_OPERATIONS <= operations


def test_incident_service_does_not_expose_backend_owned_routes() -> None:
    operations = _documented_operations()

    incorrectly_exposed_routes = {
        path
        for _, path in operations
        if path.startswith(BACKEND_OWNED_PREFIXES)
    }

    assert incorrectly_exposed_routes == set()


def test_incident_service_assigns_a_unique_operation_id_to_every_operation() -> None:
    operations = _documented_operations()
    operation_ids = _documented_operation_ids()
    operation_id_counts = Counter(operation_ids)

    duplicate_operation_ids = {
        operation_id: count
        for operation_id, count in operation_id_counts.items()
        if count > 1
    }

    assert len(operation_ids) == len(operations)
    assert duplicate_operation_ids == {}


def test_incident_service_openapi_does_not_publish_service_catalog_routes() -> None:
    paths = set(_openapi_paths())

    service_catalog_paths = {
        path
        for path in paths
        if path.startswith("/api/v1/services")
    }

    assert service_catalog_paths == set()


def test_incident_operations_publish_bearer_security() -> None:
    for path, path_item in _openapi_paths().items():
        if not path.startswith(
            "/api/v1/incidents"
        ):
            continue

        assert isinstance(
            path_item,
            dict,
        )

        for method in HTTP_METHODS:
            operation = path_item.get(
                method
            )

            if not isinstance(
                operation,
                dict,
            ):
                continue

            assert operation.get(
                "security"
            ) == [
                {
                    "ServiceBearer": [],
                }
            ]


def test_health_operation_remains_public() -> None:
    health_operation = _openapi_paths()[
        "/api/v1/health"
    ]["get"]

    assert isinstance(
        health_operation,
        dict,
    )

    assert not health_operation.get(
        "security"
    )


def test_openapi_publishes_service_bearer_scheme() -> None:
    components = app.openapi().get(
        "components"
    )

    assert isinstance(
        components,
        dict,
    )

    security_schemes = components.get(
        "securitySchemes"
    )

    assert isinstance(
        security_schemes,
        dict,
    )

    service_bearer = security_schemes.get(
        "ServiceBearer"
    )

    assert isinstance(
        service_bearer,
        dict,
    )

    assert service_bearer.get(
        "type"
    ) == "http"

    assert service_bearer.get(
        "scheme"
    ) == "bearer"

    assert service_bearer.get(
        "bearerFormat"
    ) == "JWT"