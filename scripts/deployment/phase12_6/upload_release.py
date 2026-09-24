"""Upload verified release artifacts to the TEMPORARY Terraform S3 bucket.

Run locally with AWS_REGION and RELEASE_BUCKET set from Terraform. Upload is
non-destructive: refuses to overwrite any existing release prefix.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aws(*args: str) -> str:
    proc = subprocess.run(["aws", *args], check=True, text=True, stdout=subprocess.PIPE)
    return proc.stdout.strip()


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    out = repo / ".opsflow-migration/phase12-6d"
    region = os.getenv("AWS_REGION", "")
    bucket = os.getenv("RELEASE_BUCKET", "")
    try:
        if not region or not bucket or any(x in bucket for x in ("/", ":", " ")):
            raise RuntimeError("Set AWS_REGION and a bare RELEASE_BUCKET from Terraform")
        manifest = json.loads((out / "release.json").read_text(encoding="utf-8"))
        tag = manifest["tag"]
        local_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True,
                                      capture_output=True, text=True).stdout.strip()
        if local_commit != manifest["commit"]:
            raise RuntimeError("STOP: Release manifest is not for current Git HEAD")
        checks = (out / "SHA256SUMS").read_text(encoding="ascii")
        for name, info in manifest["files"].items():
            path = (out / name) if name != "receive_release.sh" else (
                repo / "scripts/deployment/phase12_6/receive_release.sh")
            if not path.is_file() or digest(path) != info["sha256"]:
                raise RuntimeError(f"STOP: Missing or changed artifact: {name}")
            if f"{info['sha256']}  {name}\n" not in checks:
                raise RuntimeError(f"STOP: Incorrect SHA256SUMS entry: {name}")
        prefix = f"releases/{tag}/"
        existing = aws("s3api", "list-objects-v2", "--region", region, "--bucket", bucket,
                       "--prefix", prefix, "--max-keys", "1", "--query", "KeyCount", "--output", "text")
        if existing != "0":
            raise RuntimeError(f"STOP: S3 prefix already contains files: s3://{bucket}/{prefix}")
        uploads = [
            out / f"opsflow-source-{tag}.zip", out / f"opsflow-images-{tag}.tar.gz",
            repo / "scripts/deployment/phase12_6/receive_release.sh",
            out / "SHA256SUMS", out / "release.json",
        ]
        for path in uploads:
            print(f"Uploading {path.name}...", flush=True)
            aws("s3", "cp", str(path), f"s3://{bucket}/{prefix}{path.name}",
                "--region", region, "--sse", "AES256", "--only-show-errors")
        print(f"PASS: Transfer staged in s3://{bucket}/{prefix}")
        print("Do not remove the bucket until EC2 verifies the release and launch checks pass.")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        print("If upload partially succeeded, inspect prefix before attempting a controlled retry.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
