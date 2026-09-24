# cspell:words opsflow
"""Create one-time SSM recovery commands for the EXISTING uploaded release.

No Docker rebuilds, no S3 writes and no changes to the original receiver.
The original receiver is verified against both SHA256SUMS and release.json;
only an ephemeral EC2 execution copy is patched to read CRLF checksums.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from receiver_patch import patch_bytes


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_commands(
    region: str, bucket: str, tag: str, original_sha: str,
    patched_sha: str, encoded_patch: str,
) -> list[str]:
    """Build auditable, fail-closed AWS-RunShellScript instructions."""
    for value, pattern, field in (
        (region, r"[a-z]{2}(?:-gov)?-[a-z]+-\d", "region"),
        (bucket, r"[a-z0-9][a-z0-9.-]{2,62}", "bucket"),
        (tag, r"[0-9a-f]{12}", "tag"),
        (original_sha, r"[0-9a-f]{64}", "original hash"),
        (patched_sha, r"[0-9a-f]{64}", "patched hash"),
        (encoded_patch, r"[a-zA-Z0-9+/=]+", "patch payload"),
    ):
        if re.fullmatch(pattern, value) is None:
            raise ValueError(f"STOP: Invalid {field}")

    # Each element is a shell command; AWS-RunShellScript joins them with newlines.
    return [
        "set -Eeuo pipefail",
        "umask 077",
        f"export AWS_REGION='{region}' RELEASE_BUCKET='{bucket}' RELEASE_TAG='{tag}'",
        f"expected_original='{original_sha}'",
        f"expected_patched='{patched_sha}'",
        'test ! -e "/opt/opsflow/releases/$RELEASE_TAG" || { echo "STOP: Release already installed" >&2; exit 1; }',
        'prefix="s3://${RELEASE_BUCKET}/releases/${RELEASE_TAG}"',
        'aws s3 cp "${prefix}/receive_release.sh" /tmp/opsflow-receiver-original.sh --region "$AWS_REGION" --only-show-errors',
        'aws s3 cp "${prefix}/SHA256SUMS" /tmp/opsflow-receiver-checksums --region "$AWS_REGION" --only-show-errors',
        # Normalize only the CHECKSUM READER at this stage, not the release artifacts.
        'expected_list=$(tr -d \'\\r\' < /tmp/opsflow-receiver-checksums | awk \'$2 == "receive_release.sh" {print $1}\')',
        'actual_original=$(sha256sum /tmp/opsflow-receiver-original.sh | awk \'{print $1}\')',
        'test -n "$expected_list" && test "$expected_list" = "$expected_original" && test "$actual_original" = "$expected_original" || { echo "FAIL: Original S3 receiver integrity mismatch" >&2; exit 1; }',
        'echo "PASS: Original uploaded receiver matches SHA256SUMS and release.json"',
        # This exact patch program is in the repo and tested offline; pass as text,
        # never credentials. The pre- and post-patch SHA256 values are checked.
        (
            f"printf '%s' '{encoded_patch}' | base64 --decode "
            "| python3 - /tmp/opsflow-receiver-original.sh /tmp/opsflow-receiver-execution.sh"
        ),
        'actual_patched=$(sha256sum /tmp/opsflow-receiver-execution.sh | awk \'{print $1}\')',
        'test "$actual_patched" = "$expected_patched" || { echo "FAIL: Execution-copy patch integrity mismatch" >&2; exit 1; }',
        'echo "PASS: Temporary execution copy verified; original release unchanged"',
        'bash /tmp/opsflow-receiver-execution.sh',
        'rm -f /tmp/opsflow-receiver-original.sh /tmp/opsflow-receiver-execution.sh /tmp/opsflow-receiver-checksums',
    ]


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    out = repo / ".opsflow-migration" / "phase12-6d"
    manifest_path = out / "release.json"
    original_path = repo / "scripts/deployment/phase12_6/receive_release.sh"
    patch_path = Path(__file__).with_name("receiver_patch.py")
    try:
        region = os.environ.get("AWS_REGION", "")
        bucket = os.environ.get("RELEASE_BUCKET", "")
        if not manifest_path.is_file() or not original_path.is_file():
            raise ValueError("Missing original release.json or receive_release.sh")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tag = manifest["tag"]
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        if manifest["commit"] != commit or commit[:12] != tag:
            raise ValueError("Git HEAD differs from existing release. Do not commit until recovery")
        original_bytes = original_path.read_bytes()
        original_sha = manifest["files"]["receive_release.sh"]["sha256"]
        if digest(original_bytes) != original_sha:
            raise ValueError("Local original receiver differs from release.json; do not continue")
        if manifest["files"]["receive_release.sh"]["bytes"] != len(original_bytes):
            raise ValueError("Original receiver length differs from release.json")
        patched_sha = digest(patch_bytes(original_bytes))
        encoded_patch = base64.b64encode(patch_path.read_bytes()).decode("ascii")
        commands = build_commands(region, bucket, tag, original_sha, patched_sha, encoded_patch)
        output = out / "receive-ssm-params.json"
        output.write_text(
            json.dumps({"commands": commands, "executionTimeout": ["3600"]}, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"PASS: Generated one-time recovery command: {output}")
        print(f"RELEASE_TAG={tag}")
        print("No original release, S3 objects, Docker images, or database credentials were changed.")
        return 0
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
