from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import (
    Iterable,
)
from pathlib import (
    Path,
)

TRAILING_WHITESPACE_PATTERN = re.compile(
    rb"[ \t]+(?=\r?$)",
    re.MULTILINE,
)

SUPPORTED_SUFFIXES = frozenset(
    {
        ".cfg",
        ".css",
        ".dockerfile",
        ".env",
        ".example",
        ".html",
        ".ini",
        ".js",
        ".json",
        ".jsx",
        ".md",
        ".py",
        ".pyi",
        ".scss",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }
)

SUPPORTED_NAMES = frozenset(
    {
        ".gitattributes",
        ".gitignore",
        "Dockerfile",
    }
)

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "coverage",
        "dist",
        "node_modules",
    }
)


def repository_root(
) -> Path:
    """
    Return the current Git repository root.
    """

    completed_process = subprocess.run(
        [
            "git",
            "rev-parse",
            "--show-toplevel",
        ],
        check=True,
        capture_output=True,
    )

    return Path(
        os.fsdecode(
            completed_process
            .stdout
            .strip()
        )
    )


def git_paths(
    *arguments: str,
) -> set[
    Path
]:
    """
    Return NUL-delimited repository paths from one Git query.
    """

    completed_process = subprocess.run(
        [
            "git",
            *arguments,
            "-z",
        ],
        check=True,
        capture_output=True,
    )

    return {
        Path(
            os.fsdecode(
                raw_path
            )
        )
        for raw_path in (
            completed_process
            .stdout
            .split(
                b"\0"
            )
        )
        if raw_path
    }


def tracked_paths(
) -> set[
    Path
]:
    return git_paths(
        "ls-files",
    )


def untracked_paths(
) -> set[
    Path
]:
    return git_paths(
        "ls-files",
        "--others",
        "--exclude-standard",
    )


def unstaged_tracked_paths(
) -> set[
    Path
]:
    return git_paths(
        "diff",
        "--name-only",
        "--diff-filter=ACMR",
        "--",
    )


def is_supported_path(
    relative_path: Path,
) -> bool:
    """
    Return whether a path is an eligible text source file.

    Restricting the operation by filename and extension avoids
    changing binary assets or fixtures whose byte-level format
    may be significant.
    """

    if any(
        path_part
        in EXCLUDED_DIRECTORY_NAMES
        for path_part
        in relative_path.parts
    ):
        return False

    if (
        relative_path.name
        in SUPPORTED_NAMES
    ):
        return True

    return (
        relative_path
        .suffix
        .lower()
        in SUPPORTED_SUFFIXES
    )


def candidate_paths(
    *,
    mode: str,
) -> list[
    Path
]:
    if mode == "fix-unstaged":
        paths = (
            unstaged_tracked_paths()
            | untracked_paths()
        )

    elif mode in {
        "check",
        "fix-all",
    }:
        paths = (
            tracked_paths()
            | untracked_paths()
        )

    else:
        raise ValueError(
            f"Unsupported mode: {mode}"
        )

    return sorted(
        (
            path
            for path in paths
            if is_supported_path(
                path
            )
        ),
        key=lambda path: (
            path.as_posix()
        ),
    )


def remove_trailing_whitespace(
    content: bytes,
) -> bytes:
    """
    Remove spaces and tabs immediately before a line ending or
    the end of a file.

    The regular expression preserves the original LF or CRLF
    line-ending bytes.
    """

    return (
        TRAILING_WHITESPACE_PATTERN
        .sub(
            b"",
            content,
        )
    )


def changed_paths(
    *,
    root: Path,
    paths: Iterable[
        Path
    ],
    write_changes: bool,
) -> list[
    Path
]:
    changed: list[
        Path
    ] = []

    for relative_path in paths:
        absolute_path = (
            root
            / relative_path
        )

        if (
            not absolute_path.is_file()
            or absolute_path.is_symlink()
        ):
            continue

        original_content = (
            absolute_path
            .read_bytes()
        )

        # NUL bytes strongly indicate a binary file. Skip it
        # even if its filename has a supported extension.
        if b"\0" in original_content:
            continue

        normalized_content = (
            remove_trailing_whitespace(
                original_content
            )
        )

        if (
            normalized_content
            == original_content
        ):
            continue

        changed.append(
            relative_path
        )

        if write_changes:
            absolute_path.write_bytes(
                normalized_content
            )

    return changed


def parse_arguments(
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check or remove trailing spaces and tabs from "
            "OpsFlow source files."
        )
    )

    mode_group = (
        parser
        .add_mutually_exclusive_group()
    )

    mode_group.add_argument(
        "--check",
        action="store_true",
        help=(
            "Check every tracked and untracked supported "
            "source file without changing it."
        ),
    )

    mode_group.add_argument(
        "--fix-all",
        action="store_true",
        help=(
            "Fix every tracked and untracked supported "
            "source file."
        ),
    )

    mode_group.add_argument(
        "--fix-unstaged",
        action="store_true",
        help=(
            "Fix only unstaged tracked files and untracked "
            "supported source files. This is the default."
        ),
    )

    return parser.parse_args()


def main(
) -> int:
    arguments = (
        parse_arguments()
    )

    if arguments.check:
        mode = "check"

    elif arguments.fix_all:
        mode = "fix-all"

    else:
        mode = "fix-unstaged"

    root = (
        repository_root()
    )

    paths = candidate_paths(
        mode=mode
    )

    changed = changed_paths(
        root=root,
        paths=paths,
        write_changes=(
            mode
            != "check"
        ),
    )

    if mode == "check":
        if not changed:
            print(
                "Trailing-whitespace check passed."
            )

            return 0

        print(
            "Trailing whitespace was found in:",
            file=sys.stderr,
        )

        for path in changed:
            print(
                f"  {path.as_posix()}",
                file=sys.stderr,
            )

        print(
            (
                "Run: "
                "python scripts/"
                "trim_trailing_whitespace.py "
                "--fix-all"
            ),
            file=sys.stderr,
        )

        return 1

    if not changed:
        print(
            "No trailing whitespace required removal."
        )

        return 0

    for path in changed:
        print(
            "Trimmed trailing whitespace from: "
            f"{path.as_posix()}"
        )

    print(
        f"Updated {len(changed)} file(s)."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )