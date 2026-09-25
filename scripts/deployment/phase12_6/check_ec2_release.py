#!/usr/bin/env python3
"""Read-only OpsFlow release and EC2 runtime preflight for AWS-RunShellScript.

No application processes are started. Secrets stay in process memory and are
never displayed, written to disk, put in the SSM command, or logged.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

IMAGES = ("opsflow-backend", "opsflow-incident-service", "opsflow-frontend")
DB_SECRETS = (
    ("CORE_DB_SECRET_ARN", "opsflow_core_login", "opsflow"),
    ("INCIDENT_DB_SECRET_ARN", "opsflow_incidents_login", "opsflow_incidents"),
)


class PreflightError(RuntimeError):
    """A failed deployment gate; never include credentials in its message."""


def required(name: str, pattern: str | None = None) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value in {"None", "null"} or value.startswith("YOUR_"):
        raise PreflightError(f"Missing required non-secret identifier: {name}")
    if pattern and re.fullmatch(pattern, value) is None:
        raise PreflightError(f"Invalid format of non-secret identifier: {name}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checksum_entries(contents: bytes) -> dict[str, str]:
    """Parse CRLF/LF SHA256SUMS without changing the original on disk."""
    try:
        rows = contents.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise PreflightError("Checksum manifest is not ASCII") from exc
    entries: dict[str, str] = {}
    for line in rows:
        if not line:
            continue
        pair = line.split("  ", 1)
        if len(pair) != 2 or re.fullmatch(r"[a-f0-9]{64}", pair[0]) is None:
            raise PreflightError("Unexpected checksum manifest format")
        name = pair[1]
        if name in entries or "/" in name or "\\" in name or name.startswith("."):
            raise PreflightError("Unsafe or duplicate checksum entry")
        entries[name] = pair[0]
    if len(entries) != 3:
        raise PreflightError("Expected three release artifact checksums")
    return entries


def validate_secret(data: Any, expected_user: str, expected_db: str, host: str) -> None:
    """Validate metadata in memory; never print or return the password."""
    if not isinstance(data, dict):
        raise PreflightError("Runtime secret is not a JSON object")
    expected = {"engine": "postgres", "host": host, "port": 5432,
                "username": expected_user, "dbname": expected_db}
    for name, value in expected.items():
        if data.get(name) != value:
            raise PreflightError(f"Runtime secret metadata does not match: {name}")
    if not isinstance(data.get("password"), str) or len(data["password"]) < 32:
        raise PreflightError("Runtime secret password is absent or unexpectedly short")


def aws_json(region: str, *arguments: str) -> Any:
    operation = " ".join(arguments[:2])
    result = subprocess.run(
        ["aws", *arguments, "--region", region, "--output", "json"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        # Exclude stdout and stderr: AWS CLI results may contain SecretString.
        raise PreflightError(f"AWS operation failed ({operation}); inspect EC2 role permissions")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightError(f"Invalid AWS response for {operation}") from exc


def assert_expected_identity(caller_arn: str, expected_role: str) -> None:
    # IAM instance profiles result in STS assumed-role credentials on EC2.
    marker = f":assumed-role/{expected_role}/"
    if marker not in caller_arn:
        raise PreflightError("SSM command is not using the expected EC2 role")


def inspect_release(tag: str) -> Path:
    root = Path("/opt/opsflow/releases") / tag
    marker = root / ".receive_verified"
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != tag:
        raise PreflightError("Release receiver not successfully verified; STOP")
    manifest_path = root / "release.json"
    if not manifest_path.is_file():
        raise PreflightError("Installed release manifest is absent")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise PreflightError("Invalid installed release manifest") from exc
    if (manifest.get("tag") != tag or manifest.get("platform") != "linux/amd64"
            or not isinstance(manifest.get("commit"), str)
            or not manifest["commit"].startswith(tag)):
        raise PreflightError("Installed release manifest metadata disagrees with tag")
    zip_path = root / f"opsflow-source-{tag}.zip"
    if not zip_path.is_file():
        raise PreflightError("Verified source archive missing")
    files = manifest.get("files")
    expected_file = files.get(zip_path.name) if isinstance(files, dict) else None
    if (not isinstance(expected_file, dict) or sha256(zip_path) != expected_file.get("sha256")
            or zip_path.stat().st_size != expected_file.get("bytes")):
        raise PreflightError("Source archive differs from release manifest")
    checksums_path = root / "SHA256SUMS"
    if not checksums_path.is_file():
        raise PreflightError("Original checksum list is absent")
    entries = checksum_entries(checksums_path.read_bytes())
    if entries.get(zip_path.name) != sha256(zip_path):
        raise PreflightError("Source archive differs from original checksum entry")
    receiver_path = root / "receive_release.sh"
    if not receiver_path.is_file() or entries.get("receive_release.sh") != sha256(receiver_path):
        raise PreflightError("Original receiver checksum differs from stored file")
    if not (root / "app" / "compose.production.yaml").is_file():
        raise PreflightError("Production Compose file absent from installed release")
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise PreflightError("Installed source archive has corrupt members")
    return root


def inspect_docker(tag: str) -> None:
    for image in IMAGES:
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", f"{image}:{tag}"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode or result.stdout.strip() != "linux/amd64":
            raise PreflightError(f"Required Linux/amd64 image missing: {image}:{tag}")
        print(f"PASS: {image} image is linux/amd64")
    containers = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=20, check=False,
    )
    if containers.returncode:
        raise PreflightError("Unable to inspect Docker containers")
    if any(name.startswith("opsflow-") for name in containers.stdout.splitlines()):
        raise PreflightError("OpsFlow containers already running: review live deployment before proceeding")


def main() -> int:
    # getattr keeps the file analyzable in native Windows VS Code; it only runs on Linux EC2.
    get_uid = getattr(os, "geteuid", None)
    if sys.platform != "linux" or not callable(get_uid) or get_uid() != 0:
        raise PreflightError("Run only on Linux EC2 via AWS-RunShellScript as root")
    for tool in ("aws", "docker"):
        if shutil.which(tool) is None:
            raise PreflightError(f"Missing EC2 prerequisite: {tool}")
    region = required("AWS_REGION", r"[a-z]{2}(?:-gov)?-[a-z]+(?:-[a-z]+)?-\d")
    tag = required("RELEASE_TAG", r"[a-f0-9]{12}")
    host = required("RDS_HOST", r"[A-Za-z0-9][A-Za-z0-9.-]+")
    role = required("EXPECTED_EC2_ROLE", r"[A-Za-z0-9+=,.@_-]{1,64}")
    for key, _, _ in DB_SECRETS:
        required(key)

    root = inspect_release(tag)
    print(f"PASS: Installed release {tag} matches source and receiver checksums")
    inspect_docker(tag)

    caller = aws_json(region, "sts", "get-caller-identity")
    assert_expected_identity(caller.get("Arn", ""), role)
    print("PASS: EC2 instance role identity verified")

    # Read each secret into Python memory only. No passwords in argv, temp
    # files, AWS-RunShellScript parameters, stdout or exception text.
    for env_name, username, dbname in DB_SECRETS:
        raw = aws_json(
            region, "secretsmanager", "get-secret-value",
            "--secret-id", required(env_name),
            "--version-stage", "AWSCURRENT", "--query", "SecretString",
        )
        if not isinstance(raw, str):
            raise PreflightError(f"{dbname} secret is not a string")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PreflightError(f"{dbname} secret contains invalid JSON") from exc
        validate_secret(payload, username, dbname, host)
        del payload, raw
        print(f"PASS: EC2 may retrieve and validate {dbname} secret (value not displayed)")

    try:
        with socket.create_connection((host, 5432), timeout=5):
            pass
    except OSError as exc:
        raise PreflightError("EC2 cannot reach the private RDS host on TCP 5432") from exc
    print("PASS: Private RDS TCP 5432 reachable (TLS and SQL verification still pending)")

    usage = shutil.disk_usage("/")
    if usage.free < 4 * 1024**3:
        raise PreflightError("Less than 4 GiB free on EC2; inspect storage before launching containers")
    print("PASS: More than 4 GiB host disk space is free")
    print("PASS: Release and secret-access preflight complete; no containers started")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PreflightError as error:
        print(f"STOP: {error}", file=sys.stderr)
        raise SystemExit(1) from None
