from __future__ import annotations

import argparse
import hashlib
import io
import os
from pathlib import Path
from zipfile import (
    ZIP_DEFLATED,
    ZipFile,
    ZipInfo,
)

REPOSITORY_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)

DIST_DIRECTORY = (
    REPOSITORY_ROOT
    / "lambdas"
    / "realtime-notifier"
    / "dist"
)

BUNDLE_PATH = (
    DIST_DIRECTORY
    / "index.js"
)

ARCHIVE_PATH = (
    DIST_DIRECTORY
    / "realtime-notifier.zip"
)

ARCHIVE_MEMBER_NAME = (
    "index.js"
)

# ZIP's portable DOS timestamp range begins in 1980.
#
# Using one fixed timestamp prevents the archive hash from
# changing merely because packaging was executed at a
# different wall-clock time.
FIXED_ZIP_TIMESTAMP = (
    1980,
    1,
    1,
    0,
    0,
    0,
)

# Regular file with 0644 permissions.
FIXED_FILE_MODE = (
    0o100644
)


class RealtimeNotifierPackageError(
    RuntimeError
):
    pass


def sha256_bytes(
    value: bytes,
) -> str:
    return (
        hashlib.sha256(
            value
        )
        .hexdigest()
    )


def build_archive_bytes(
    bundle: bytes,
) -> bytes:
    """
    Build one deterministic Lambda ZIP archive.

    Determinism requires every ZIP field that can otherwise
    vary between runs to be controlled explicitly:

    - archive member name
    - modification timestamp
    - file mode
    - compression algorithm
    - compression level
    - creator platform

    The resulting archive contains exactly one root-level
    member:

        index.js
    """

    buffer = (
        io.BytesIO()
    )

    member = (
        ZipInfo(
            filename=(
                ARCHIVE_MEMBER_NAME
            ),
            date_time=(
                FIXED_ZIP_TIMESTAMP
            ),
        )
    )

    member.compress_type = (
        ZIP_DEFLATED
    )

    # Unix creator system.
    #
    # Explicitly fixing this avoids Windows/Linux packaging
    # differences in external file attributes.
    member.create_system = 3

    member.external_attr = (
        FIXED_FILE_MODE
        << 16
    )

    with ZipFile(
        buffer,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr(
            member,
            bundle,
            compress_type=ZIP_DEFLATED,
            compresslevel=9,
        )

    return (
        buffer.getvalue()
    )


def expected_archive_bytes() -> bytes:
    if not BUNDLE_PATH.is_file():
        raise RealtimeNotifierPackageError(
            "Realtime notifier bundle is missing: "
            f"{BUNDLE_PATH}"
        )

    bundle = (
        BUNDLE_PATH
        .read_bytes()
    )

    first = (
        build_archive_bytes(
            bundle
        )
    )

    second = (
        build_archive_bytes(
            bundle
        )
    )

    if first != second:
        raise RealtimeNotifierPackageError(
            "Deterministic packaging invariant failed: "
            "identical bundle bytes produced different "
            "archive bytes."
        )

    return first


def verify_archive_contents(
    archive_bytes: bytes,
) -> None:
    with ZipFile(
        io.BytesIO(
            archive_bytes
        ),
        mode="r",
    ) as archive:
        names = (
            archive.namelist()
        )

        if names != [
            ARCHIVE_MEMBER_NAME
        ]:
            raise RealtimeNotifierPackageError(
                "Unexpected Lambda archive contents: "
                f"{names!r}"
            )

        packaged_bundle = (
            archive.read(
                ARCHIVE_MEMBER_NAME
            )
        )

    source_bundle = (
        BUNDLE_PATH
        .read_bytes()
    )

    if (
        packaged_bundle
        != source_bundle
    ):
        raise RealtimeNotifierPackageError(
            "Packaged index.js does not match "
            "dist/index.js."
        )


def write_archive(
    archive_bytes: bytes,
) -> None:
    DIST_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        ARCHIVE_PATH
        .with_suffix(
            ".zip.tmp"
        )
    )

    try:
        temporary_path.write_bytes(
            archive_bytes
        )

        os.replace(
            temporary_path,
            ARCHIVE_PATH,
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def check_existing_archive(
    expected: bytes,
) -> None:
    if not ARCHIVE_PATH.is_file():
        raise RealtimeNotifierPackageError(
            "Realtime notifier deployment archive "
            "is missing: "
            f"{ARCHIVE_PATH}"
        )

    actual = (
        ARCHIVE_PATH
        .read_bytes()
    )

    if actual != expected:
        raise RealtimeNotifierPackageError(
            "Realtime notifier deployment archive "
            "is not reproducible from the current "
            "dist/index.js."
        )

    verify_archive_contents(
        actual
    )


def print_summary(
    archive_bytes: bytes,
) -> None:
    bundle = (
        BUNDLE_PATH
        .read_bytes()
    )

    print(
        "Realtime notifier package verified."
    )

    print(
        "Bundle:",
        BUNDLE_PATH,
    )

    print(
        "Archive:",
        ARCHIVE_PATH,
    )

    print(
        "Bundle SHA256:",
        sha256_bytes(
            bundle
        ),
    )

    print(
        "Archive SHA256:",
        sha256_bytes(
            archive_bytes
        ),
    )

    print(
        "Archive member:",
        ARCHIVE_MEMBER_NAME,
    )

    print(
        "Archive timestamp:",
        "-".join(
            str(value)
            for value
            in FIXED_ZIP_TIMESTAMP
        ),
    )


def parse_arguments() -> argparse.Namespace:
    parser = (
        argparse.ArgumentParser(
            description=(
                "Build or verify the deterministic "
                "OpsFlow realtime notifier Lambda ZIP."
            )
        )
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Verify that the existing deployment ZIP "
            "exactly matches the deterministic archive "
            "generated from dist/index.js."
        ),
    )

    return (
        parser.parse_args()
    )


def main() -> int:
    args = (
        parse_arguments()
    )

    try:
        expected = (
            expected_archive_bytes()
        )

        verify_archive_contents(
            expected
        )

        if args.check:
            check_existing_archive(
                expected
            )
        else:
            write_archive(
                expected
            )

            check_existing_archive(
                expected
            )

        print_summary(
            expected
        )

        return 0

    except RealtimeNotifierPackageError as error:
        print(
            f"ERROR: {error}"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
