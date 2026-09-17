from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_PATHS = (
    Path(".env.docker.example"),
    Path("compose.yaml"),
    Path("backend/.env.example"),
    Path("backend/app"),
    Path("incident-service/.env.example"),
    Path("incident-service/app"),
)

RETIRED_IDENTIFIERS = (
    "INCIDENT_SERVICE_TOKEN",
    "X-OpsFlow-Internal-Token",
    "incident_service_token",
)


def source_files(
    path: Path,
) -> tuple[Path, ...]:
    absolute_path = REPOSITORY_ROOT / path

    if absolute_path.is_file():
        return (absolute_path,)

    return tuple(
        candidate
        for candidate in absolute_path.rglob("*")
        if (
            candidate.is_file()
            and candidate.suffix == ".py"
        )
    )


def main() -> None:
    violations: list[str] = []

    for configured_path in PRODUCTION_PATHS:
        for source_path in source_files(
            configured_path
        ):
            content = source_path.read_text(
                encoding="utf-8"
            )

            for line_number, line in enumerate(
                content.splitlines(),
                start=1,
            ):
                for identifier in RETIRED_IDENTIFIERS:
                    if identifier in line:
                        relative_path = source_path.relative_to(
                            REPOSITORY_ROOT
                        )
                        violations.append(
                            f"{relative_path}:{line_number}: "
                            f"retired identifier {identifier!r}"
                        )

    if violations:
        formatted_violations = "\n".join(
            violations
        )
        raise SystemExit(
            "Distributed-authentication contract violations found:\n"
            f"{formatted_violations}"
        )

    print(
        "Distributed-authentication production contract passed."
    )


if __name__ == "__main__":
    main()
