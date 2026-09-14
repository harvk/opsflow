from __future__ import annotations

from typing import (
    Any,
)

from app.main import (
    app,
)


def get_overview_operation(
) -> dict[str, Any]:
    openapi_schema = (
        app.openapi()
    )

    paths = (
        openapi_schema[
            "paths"
        ]
    )

    overview_path = paths[
        "/api/v1/overview"
    ]

    operation = overview_path[
        "get"
    ]

    assert isinstance(
        operation,
        dict,
    )

    return operation


def test_overview_route_is_registered(
) -> None:
    operation = (
        get_overview_operation()
    )

    assert operation[
        "tags"
    ] == [
        "Overview"
    ]


def test_overview_route_uses_overview_response_schema(
) -> None:
    operation = (
        get_overview_operation()
    )

    response_schema = (
        operation[
            "responses"
        ][
            "200"
        ][
            "content"
        ][
            "application/json"
        ][
            "schema"
        ]
    )

    schema_reference = (
        response_schema.get(
            "$ref"
        )
    )

    assert isinstance(
        schema_reference,
        str,
    )

    assert schema_reference.endswith(
        "/OverviewResponse"
    )


def test_overview_route_requires_authentication(
) -> None:
    operation = (
        get_overview_operation()
    )

    security_requirements = (
        operation.get(
            "security"
        )
    )

    assert isinstance(
        security_requirements,
        list,
    )

    assert (
        security_requirements
        != []
    )