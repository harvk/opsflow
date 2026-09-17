from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

EXPECTED_SECRETS = {
    "backend": {
        "core_service_identity_private_key": (
            "core_service_identity_private_key"
        ),
        "incident_service_identity_public_key": (
            "incident_service_identity_public_key"
        ),
    },
    "incident-service": {
        "core_service_identity_public_key": (
            "core_service_identity_public_key"
        ),
        "incident_service_identity_private_key": (
            "incident_service_identity_private_key"
        ),
    },
}

EXPECTED_ENVIRONMENT = {
    "backend": {
        "SERVICE_IDENTITY_PRIVATE_KEY_PATH": (
            "/run/secrets/core_service_identity_private_key"
        ),
        "INCIDENT_SERVICE_IDENTITY_PUBLIC_KEY_PATH": (
            "/run/secrets/incident_service_identity_public_key"
        ),
    },
    "incident-service": {
        "SERVICE_IDENTITY_PUBLIC_KEY_FILE": (
            "/run/secrets/core_service_identity_public_key"
        ),
        "SERVICE_IDENTITY_SIGNING_PRIVATE_KEY_PATH": (
            "/run/secrets/incident_service_identity_private_key"
        ),
    },
}

ALL_IDENTITY_SECRETS = {
    "core_service_identity_private_key",
    "core_service_identity_public_key",
    "incident_service_identity_private_key",
    "incident_service_identity_public_key",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate service-identity key isolation in the "
            "rendered Docker Compose configuration."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env.docker"),
        help="Compose environment file. Defaults to .env.docker.",
    )
    return parser.parse_args()


def rendered_compose_configuration(
    env_file: Path,
) -> dict[str, Any]:
    completed_process = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "config",
            "--format",
            "json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if completed_process.returncode != 0:
        message = completed_process.stderr.strip()
        raise SystemExit(
            "Docker Compose configuration could not be rendered:\n"
            f"{message}"
        )

    return json.loads(
        completed_process.stdout
    )


def mounted_secrets(
    service: dict[str, Any],
) -> dict[str, str]:
    mounts: dict[str, str] = {}

    for secret in service.get(
        "secrets",
        [],
    ):
        if isinstance(secret, str):
            mounts[secret] = secret
            continue

        source = secret.get("source")
        target = secret.get("target", source)

        if source and target:
            mounts[source] = target

    return mounts


def validate_service(
    service_name: str,
    service: dict[str, Any],
) -> list[str]:
    violations: list[str] = []
    actual_mounts = mounted_secrets(
        service
    )
    identity_mounts = {
        source: target
        for source, target in actual_mounts.items()
        if source in ALL_IDENTITY_SECRETS
    }
    expected_mounts = EXPECTED_SECRETS[
        service_name
    ]

    if identity_mounts != expected_mounts:
        violations.append(
            f"{service_name}: expected identity secret mounts "
            f"{expected_mounts!r}, found {identity_mounts!r}"
        )

    environment = service.get(
        "environment",
        {},
    )

    for variable, expected_value in EXPECTED_ENVIRONMENT[
        service_name
    ].items():
        actual_value = environment.get(
            variable
        )

        if actual_value != expected_value:
            violations.append(
                f"{service_name}: {variable} must equal "
                f"{expected_value!r}, found {actual_value!r}"
            )

    return violations


def main() -> None:
    arguments = parse_arguments()
    configuration = rendered_compose_configuration(
        arguments.env_file
    )
    services = configuration.get(
        "services",
        {},
    )
    configured_secrets = set(
        configuration.get(
            "secrets",
            {}
        )
    )
    violations: list[str] = []

    missing_secrets = (
        ALL_IDENTITY_SECRETS
        - configured_secrets
    )

    if missing_secrets:
        violations.append(
            "Missing top-level identity secrets: "
            + ", ".join(
                sorted(
                    missing_secrets
                )
            )
        )

    for service_name in EXPECTED_SECRETS:
        service = services.get(
            service_name
        )

        if service is None:
            violations.append(
                f"Missing Compose service: {service_name}"
            )
            continue

        violations.extend(
            validate_service(
                service_name,
                service,
            )
        )

    if violations:
        raise SystemExit(
            "Service-identity Compose boundary violations found:\n"
            + "\n".join(
                f"- {violation}"
                for violation in violations
            )
        )

    print(
        "Service-identity Compose key boundaries passed."
    )


if __name__ == "__main__":
    main()
