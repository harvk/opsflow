from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

APP_ROOT = (
    BACKEND_ROOT
    / "app"
)


def _source(
    relative_path: str,
) -> str:
    return (
        APP_ROOT
        .joinpath(
            relative_path
        )
        .read_text(
            encoding="utf-8"
        )
    )


def _syntax_tree(
    relative_path: str,
) -> ast.Module:
    return ast.parse(
        _source(
            relative_path
        ),
        filename=(
            str(
                APP_ROOT
                / relative_path
            )
        ),
    )


def _imported_modules(
    relative_path: str,
) -> set[str]:
    modules: set[str] = set()

    for node in ast.walk(
        _syntax_tree(
            relative_path
        )
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            modules.update(
                alias.name
                for alias in node.names
            )

        elif (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module is not None
        ):
            modules.add(
                node.module
            )

    return modules


def _names_imported_from(
    relative_path: str,
    module_name: str,
) -> set[str]:
    imported_names: set[str] = set()

    for node in ast.walk(
        _syntax_tree(
            relative_path
        )
    ):
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
            == module_name
        ):
            imported_names.update(
                alias.name
                for alias in node.names
            )

    return imported_names


def _called_attribute_names(
    relative_path: str,
) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(
            _syntax_tree(
                relative_path
            )
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
        )
    }


def _is_disallowed_contract_import(
    module_name: str,
) -> bool:
    disallowed_roots = (
        "fastapi",
        "httpx",
        "sqlalchemy",
        "app.db",
        "app.models",
        "app.repositories",
    )

    return any(
        module_name == root
        or module_name.startswith(
            f"{root}."
        )
        for root in disallowed_roots
    )


def test_incident_routes_depend_on_gateway_not_service(
) -> None:
    route_files = (
        "api/routes/incidents.py",
        "api/routes/services.py",
    )

    for route_file in route_files:
        dependency_names = (
            _names_imported_from(
                route_file,
                "app.api.dependencies",
            )
        )

        assert (
            "IncidentGatewayDependency"
            in dependency_names
        )

        assert (
            "IncidentServiceDependency"
            not in dependency_names
        )

        assert (
            "get_incident_service"
            not in dependency_names
        )


def test_incident_service_depends_on_service_catalog_gateway(
) -> None:
    imported_modules = (
        _imported_modules(
            "services/incident_service.py"
        )
    )

    assert (
        "app.gateways.service_catalog_gateway"
        in imported_modules
    )

    assert (
        "app.repositories.service_repository"
        not in imported_modules
    )


def test_gateway_contracts_are_framework_and_persistence_independent(
) -> None:
    contract_files = (
        "gateways/incident_gateway.py",
        "gateways/service_catalog_gateway.py",
    )

    for contract_file in contract_files:
        disallowed_imports = {
            module_name
            for module_name in (
                _imported_modules(
                    contract_file
                )
            )
            if (
                _is_disallowed_contract_import(
                    module_name
                )
            )
        }

        assert (
            disallowed_imports
            == set()
        ), (
            f"{contract_file} contains "
            "boundary-breaking imports: "
            f"{sorted(disallowed_imports)}"
        )


def test_incident_repository_does_not_cross_service_or_transaction_boundary(
) -> None:
    repository_file = (
        "repositories/"
        "sqlalchemy_incident_repository.py"
    )

    imported_modules = (
        _imported_modules(
            repository_file
        )
    )

    assert (
        "app.models.service"
        not in imported_modules
    )

    assert (
        "ServiceModel"
        not in _source(
            repository_file
        )
    )

    transaction_calls = (
        _called_attribute_names(
            repository_file
        )
        & {
            "commit",
            "rollback",
        }
    )

    assert (
        transaction_calls
        == set()
    ), (
        "Incident repository must not own transaction "
        f"completion: {sorted(transaction_calls)}"
    )


def test_local_adapters_are_the_explicit_monolith_bridges(
) -> None:
    local_incident_imports = (
        _imported_modules(
            "gateways/"
            "local_incident_gateway.py"
        )
    )

    local_catalog_imports = (
        _imported_modules(
            "gateways/"
            "local_service_catalog_gateway.py"
        )
    )

    assert (
        "app.services.incident_service"
        in local_incident_imports
    )

    assert (
        "app.repositories.service_repository"
        in local_catalog_imports
    )


def test_dependency_wiring_selects_local_gateway_adapters(
) -> None:
    dependency_imports = (
        _imported_modules(
            "api/dependencies.py"
        )
    )

    assert (
        "app.gateways.local_incident_gateway"
        in dependency_imports
    )

    assert (
        "app.gateways.local_service_catalog_gateway"
        in dependency_imports
    )