#!/usr/bin/env python3
"""Generate non-secret AWS-RunShellScript parameters for runtime readiness.

Uses the ORIGINAL 12.6D release manifest, not current HEAD, since post-release
hotfix commits may legitimately have advanced the branch.
"""
from __future__ import annotations

import base64
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def read_command(*args: str, cwd: Path | None = None) -> str:
    process = subprocess.run(args, cwd=cwd, capture_output=True,
                             text=True, timeout=30, check=False)
    if process.returncode:
        raise RuntimeError(f"Command returned nonzero: {args[0]} (details suppressed)")
    result = process.stdout.strip()
    if not result or result == "None":
        raise RuntimeError(f"Missing expected output from: {args[0]}")
    return result


def build_commands(script: bytes, identifiers: dict[str, str]) -> list[str]:
    patterns = {
        "AWS_REGION": r"[a-z]{2}(?:-gov)?-[a-z]+(?:-[a-z]+)?-\d",
        "RELEASE_TAG": r"[a-f0-9]{12}",
        "RDS_HOST": r"[A-Za-z0-9][A-Za-z0-9.-]+",
        "EXPECTED_EC2_ROLE": r"[A-Za-z0-9+=,.@_-]{1,64}",
        "CORE_DB_SECRET_ARN": r"arn:aws[a-z-]*:secretsmanager:[^:]+:\d{12}:secret:[A-Za-z0-9/_+=.@-]+",
        "INCIDENT_DB_SECRET_ARN": r"arn:aws[a-z-]*:secretsmanager:[^:]+:\d{12}:secret:[A-Za-z0-9/_+=.@-]+",
    }
    if set(identifiers) != set(patterns):
        raise ValueError("Missing or additional non-secret preflight identifiers")
    for key, pattern in patterns.items():
        if re.fullmatch(pattern, identifiers[key]) is None:
            raise ValueError(f"Invalid identifier: {key}")
    if not script.startswith(b"#!/usr/bin/env python3"):
        raise ValueError("Invalid EC2 preflight script header")
    exports = " ".join(f"{key}={shlex.quote(value)}" for key, value in identifiers.items())
    encoded = base64.b64encode(script).decode("ascii")
    return ["set -Eeuo pipefail", f"export {exports}",
            f"printf '%s' '{encoded}' | base64 --decode | python3 -"]


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    tf = repo / "infrastructure" / "terraform"
    release = repo / ".opsflow-migration" / "phase12-6d" / "release.json"
    script = Path(__file__).with_name("check_ec2_release.py")
    if not release.is_file() or not script.is_file():
        raise RuntimeError("Existing original release.json or preflight script is missing")
    metadata = json.loads(release.read_text(encoding="utf-8"))
    tag = metadata.get("tag", "")
    identifiers = {
        "AWS_REGION": read_command("terraform", "output", "-raw", "aws_region", cwd=tf),
        "RELEASE_TAG": tag,
        "RDS_HOST": read_command("terraform", "output", "-raw", "live_rds_endpoint", cwd=tf),
        "CORE_DB_SECRET_ARN": read_command("terraform", "output", "-raw", "live_core_database_secret_arn", cwd=tf),
        "INCIDENT_DB_SECRET_ARN": read_command("terraform", "output", "-raw", "live_incident_database_secret_arn", cwd=tf),
    }
    profile = read_command("terraform", "output", "-raw", "live_ec2_instance_profile_name", cwd=tf)
    identifiers["EXPECTED_EC2_ROLE"] = read_command(
        "aws", "iam", "get-instance-profile", "--instance-profile-name", profile,
        "--query", "InstanceProfile.Roles[0].RoleName", "--output", "text",
    )
    instance_id = read_command("terraform", "output", "-raw", "live_ec2_instance_id", cwd=tf)
    if re.fullmatch(r"i-[a-f0-9]{8,17}", instance_id) is None:
        raise RuntimeError("Invalid EC2 instance ID from Terraform")
    commands = build_commands(script.read_bytes(), identifiers)
    target = repo / ".opsflow-migration" / "phase12-6d" / "runtime-preflight-ssm-params.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"commands": commands, "executionTimeout": ["600"]}, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"PASS: Non-secret SSM preflight parameters created at {target}")
    print(f"INSTANCE_ID={instance_id}")
    print(f"AWS_REGION={identifiers['AWS_REGION']}")
    print(f"RELEASE_TAG={tag}")
    print("No DB password, signing key or production env file appears in this command.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        raise SystemExit(1) from None
