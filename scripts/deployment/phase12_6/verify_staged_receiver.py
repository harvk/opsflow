"""Read-only diagnostic for OpsFlow release receiver staged in temporary S3.

Windows Git Bash, from repository root:
    export AWS_REGION=us-east-1 RELEASE_BUCKET=<terraform output bucket>
    backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/verify_staged_receiver.py
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    release = repo / ".opsflow-migration" / "phase12-6d"
    region = os.environ.get("AWS_REGION", "")
    bucket = os.environ.get("RELEASE_BUCKET", "")
    if not region or not bucket:
        print("STOP: Set AWS_REGION and RELEASE_BUCKET from Terraform.", file=sys.stderr)
        return 1
    try:
        manifest = json.loads((release / "release.json").read_text(encoding="utf-8"))
        tag = manifest["tag"]
        expected = manifest["files"]["receive_release.sh"]["sha256"]
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("Invalid expected receiver digest")
        current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                 check=True, capture_output=True, text=True).stdout.strip()
        if current != manifest["commit"]:
            raise ValueError("Current HEAD has changed since release; stop and preserve existing release")
        with tempfile.TemporaryDirectory(prefix="opsflow-s3-audit-") as temporary:
            target = Path(temporary)
            prefix = f"s3://{bucket}/releases/{tag}/"
            for name in ("receive_release.sh", "SHA256SUMS"):
                subprocess.run(["aws", "s3", "cp", prefix + name,
                                str(target / name), "--region", region, "--only-show-errors"],
                               check=True)
            entries = {}
            sums = (target / "SHA256SUMS").read_bytes()
            for line in sums.decode("ascii").splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    entries[parts[1].strip().lstrip("*")] = parts[0]
            actual_remote = sha256((target / "receive_release.sh").read_bytes())
            actual_local = sha256((repo / "scripts/deployment/phase12_6/receive_release.sh").read_bytes())
            entry = entries.get("receive_release.sh", "")
            print(f"Checksum-list size: {len(sums)} bytes")
            print(f"Checksum-list CRLF lines: {sums.count(bytes([13, 10]))}")
            print(f"Manifest/S3 checksum entry: {'PASS' if expected == entry else 'FAIL'}")
            print(f"Manifest/S3 receiver content: {'PASS' if expected == actual_remote else 'FAIL'}")
            print(f"Manifest/local receiver content: {'PASS' if expected == actual_local else 'FAIL'}")
            if not (expected == entry == actual_remote == actual_local):
                raise ValueError("S3 receiver differs; do not retry the transfer or overwrite S3")
        print("PASS: Existing S3 receiver is valid; use corrected SSM command generation")
        return 0
    except (KeyError, ValueError, OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
