from __future__ import annotations

import re

from pathlib import (
    Path,
)

from app.core.password_policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
)


# =========================================================
# REPOSITORY PATHS
# =========================================================
#
# File location:
#
#     repo/
#       backend/
#         tests/
#           test_password_policy_cross_stack_contract.py
#
# Path(__file__).resolve().parents[2] therefore points to the
# repository root.
# =========================================================


REPOSITORY_ROOT = (
    Path(
        __file__
    )
    .resolve()
    .parents[
        2
    ]
)

FRONTEND_SOURCE_ROOT = (
    REPOSITORY_ROOT
    / "frontend"
    / "src"
)

FRONTEND_AUTH_DIRECTORY = (
    FRONTEND_SOURCE_ROOT
    / "auth"
)

FRONTEND_PASSWORD_POLICY_PATH = (
    FRONTEND_AUTH_DIRECTORY
    / "passwordPolicy.ts"
)


# =========================================================
# EXPORTED INTEGER EXTRACTION
# =========================================================


def extract_exported_integer(
    source: str,
    *,
    constant_name: str,
) -> int:
    """
    Read one exported integer constant from the TypeScript
    password-policy module.

    Expected shape:

        export const PASSWORD_MIN_LENGTH = 15;

    Whitespace may span lines, so formatting changes do not
    break this contract test.
    """

    pattern = (
        re.compile(
            (
                r"\bexport\s+const\s+"
                + re.escape(
                    constant_name
                )
                + r"\s*=\s*(\d+)\s*;"
            ),
            flags=(
                re.MULTILINE
            ),
        )
    )

    matches = (
        pattern.findall(
            source
        )
    )

    assert (
        len(
            matches
        )
        == 1
    ), (
        f"Expected exactly one exported "
        f"{constant_name} constant in "
        f"{FRONTEND_PASSWORD_POLICY_PATH}, "
        f"but found {len(matches)}."
    )

    return int(
        matches[
            0
        ]
    )


# =========================================================
# FRONTEND POLICY READER
# =========================================================


def read_frontend_password_policy(
) -> str:
    """
    Read the frontend password-policy source.

    Failure to find this file is intentional: if the module
    is renamed or removed, the cross-stack security contract
    should fail loudly rather than silently stop checking
    drift.
    """

    assert (
        FRONTEND_PASSWORD_POLICY_PATH
        .is_file()
    ), (
        "Frontend password-policy module was not found at "
        f"{FRONTEND_PASSWORD_POLICY_PATH}."
    )

    return (
        FRONTEND_PASSWORD_POLICY_PATH
        .read_text(
            encoding="utf-8"
        )
    )


# =========================================================
# CROSS-STACK LENGTH CONTRACT
# =========================================================


def test_frontend_password_policy_matches_backend_authority(
) -> None:
    """
    The Python backend remains the authoritative password
    policy.

    The React policy module is a client-side UX mirror and
    must advertise exactly the same length boundaries.
    """

    frontend_source = (
        read_frontend_password_policy()
    )

    frontend_minimum = (
        extract_exported_integer(
            frontend_source,
            constant_name=(
                "PASSWORD_MIN_LENGTH"
            ),
        )
    )

    frontend_maximum = (
        extract_exported_integer(
            frontend_source,
            constant_name=(
                "PASSWORD_MAX_LENGTH"
            ),
        )
    )

    assert (
        frontend_minimum
        == PASSWORD_MIN_LENGTH
    ), (
        "Frontend/backend password-policy drift detected: "
        "PASSWORD_MIN_LENGTH differs. "
        f"Backend={PASSWORD_MIN_LENGTH}, "
        f"Frontend={frontend_minimum}."
    )

    assert (
        frontend_maximum
        == PASSWORD_MAX_LENGTH
    ), (
        "Frontend/backend password-policy drift detected: "
        "PASSWORD_MAX_LENGTH differs. "
        f"Backend={PASSWORD_MAX_LENGTH}, "
        f"Frontend={frontend_maximum}."
    )


# =========================================================
# CANONICAL FILE CASING
# =========================================================


def test_frontend_password_policy_uses_canonical_file_casing(
) -> None:
    """
    Protect the exact casing we just standardized.

    Windows normally uses a case-insensitive filesystem,
    while Linux CI/build environments are typically
    case-sensitive.

    Therefore:

        passwordPolicy.ts

    and:

        PasswordPolicy.ts

    must never be allowed to coexist conceptually in the
    TypeScript module graph.

    Directory enumeration is used instead of Path.exists()
    for the uppercase variant because Windows may resolve a
    differently cased path to the same file.
    """

    assert (
        FRONTEND_AUTH_DIRECTORY
        .is_dir()
    )

    filenames = {
        entry.name
        for entry
        in FRONTEND_AUTH_DIRECTORY
        .iterdir()
        if entry.is_file()
    }

    assert (
        "passwordPolicy.ts"
        in filenames
    ), (
        "Expected canonical frontend policy filename "
        "'passwordPolicy.ts'."
    )

    assert (
        "PasswordPolicy.ts"
        not in filenames
    ), (
        "Found incorrectly cased 'PasswordPolicy.ts'. "
        "The canonical filename is 'passwordPolicy.ts'."
    )


# =========================================================
# IMPORT CASING
# =========================================================


def test_frontend_source_does_not_import_uppercase_password_policy(
) -> None:
    """
    Prevent the TS1261 casing regression that occurs when
    one source file imports:

        ../auth/passwordPolicy

    while another imports:

        ../auth/PasswordPolicy

    We scan TypeScript import declarations throughout src/
    for the incorrect uppercase module spelling.
    """

    uppercase_import_pattern = (
        re.compile(
            (
                r"\bfrom\s+"
                r"""["']"""
                r"""[^"']*"""
                r"PasswordPolicy"
                r"""["']"""
            )
        )
    )

    offending_files: list[
        str
    ] = []

    for path in (
        FRONTEND_SOURCE_ROOT
        .rglob(
            "*"
        )
    ):
        if (
            not path.is_file()
            or path.suffix
            not in {
                ".ts",
                ".tsx",
            }
        ):
            continue

        source = (
            path.read_text(
                encoding="utf-8"
            )
        )

        if (
            uppercase_import_pattern
            .search(
                source
            )
            is not None
        ):
            offending_files.append(
                str(
                    path.relative_to(
                        REPOSITORY_ROOT
                    )
                )
            )

    assert (
        offending_files
        == []
    ), (
        "Incorrectly cased PasswordPolicy import found in: "
        + ", ".join(
            offending_files
        )
    )