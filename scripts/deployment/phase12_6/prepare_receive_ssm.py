"""Create an SSM Run Command parameters file for long-running EC2 transfer.

Needs AWS_REGION and RELEASE_BUCKET, reads tag from current Git HEAD.
Only non-secret infrastructure identifiers are sent through Systems Manager.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    region = os.getenv("AWS_REGION", "")
    bucket = os.getenv("RELEASE_BUCKET", "")
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        print("FAIL: Set AWS_REGION from Terraform", file=sys.stderr)
        return 1
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{2,62}", bucket):
        print("FAIL: Set a bare RELEASE_BUCKET from Terraform", file=sys.stderr)
        return 1
    tag = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         text=True, check=True, capture_output=True).stdout.strip()[:12]
    if not re.fullmatch("[0-9a-f]{12}", tag):
        print("FAIL: Invalid release tag", file=sys.stderr)
        return 1
    out = repo / ".opsflow-migration/phase12-6d"
    manifest = out / "release.json"
    if not manifest.is_file() or json.loads(manifest.read_text(encoding="utf-8"))["tag"] != tag:
        print("FAIL: release.json missing or tag does not match current HEAD", file=sys.stderr)
        return 1
    # These three strings are regex-validated, so direct assignment is safe.
    commands = [
        "set -Eeuo pipefail",
        "umask 077",
        f"export AWS_REGION='{region}' RELEASE_BUCKET='{bucket}' RELEASE_TAG='{tag}'",
        "prefix=\"s3://${RELEASE_BUCKET}/releases/${RELEASE_TAG}\"",
        "aws s3 cp \"${prefix}/receive_release.sh\" /tmp/receive_release.sh --region \"$AWS_REGION\" --only-show-errors",
        "aws s3 cp \"${prefix}/SHA256SUMS\" /tmp/opsflow-receive-SHA256SUMS --region \"$AWS_REGION\" --only-show-errors",
        "expected=$(awk '$2 == \"receive_release.sh\" {print $1}' /tmp/opsflow-receive-SHA256SUMS)",
        "actual=$(sha256sum /tmp/receive_release.sh | awk '{print $1}')",
        "test -n \"$expected\" && test \"$expected\" = \"$actual\" || { echo 'FAIL: Receiver checksum mismatch' >&2; exit 1; }",
        "bash /tmp/receive_release.sh",
        "rm -f /tmp/receive_release.sh /tmp/opsflow-receive-SHA256SUMS",
    ]
    dest = out / "receive-ssm-params.json"
    dest.write_text(json.dumps({"commands": commands, "executionTimeout": ["3600"]}, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: Created {dest}")
    print("No database secrets or passwords are included.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
