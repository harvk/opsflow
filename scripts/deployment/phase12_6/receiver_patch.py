"""One-time, byte-exact CRLF recovery for an already verified OpsFlow release receiver.

Only the *execution copy* on EC2 is changed. Original S3 objects, original
receiver file, source archive, images, checksums and release.json stay intact.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ANCHOR = b"  sha256sum -c SHA256SUMS\n"
REPLACEMENT = (
    b"  tr -d '\\r' < SHA256SUMS > SHA256SUMS.lf\n"
    b"  sha256sum -c SHA256SUMS.lf\n"
)


def patch_bytes(original: bytes) -> bytes:
    if original.count(ANCHOR) != 1:
        raise ValueError(
            "STOP: Original receiver does not have exactly one expected checksum command; "
            "do not patch an unknown version"
        )
    return original.replace(ANCHOR, REPLACEMENT, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("execution_copy", type=Path)
    args = parser.parse_args()
    if args.original.resolve() == args.execution_copy.resolve():
        parser.error("Must not overwrite the verified original receiver")
    original = args.original.read_bytes()
    patched = patch_bytes(original)
    args.execution_copy.write_bytes(patched)
    args.execution_copy.chmod(0o700)
    print("PASS: Patched only the temporary receiver execution copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
