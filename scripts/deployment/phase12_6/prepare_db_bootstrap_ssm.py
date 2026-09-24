#!/usr/bin/env python3
"""Prepare a non-secret AWS Systems Manager Run Command payload locally.

Run from repository root with backend/.venv/Scripts/python.exe on Windows.
The produced JSON embeds SCRIPT SOURCE + resource ARNs, NEVER passwords.
"""
from __future__ import annotations

import base64
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TF_DIR = ROOT / "infrastructure" / "terraform"
SCRIPT = Path(__file__).with_name("bootstrap_db_roles.py")
OUT = ROOT / ".opsflow-migration" / "phase12-6b-ssm-params.json"


def tf_output(name: str) -> str:
    result = subprocess.run(
        ["terraform", "output", "-raw", name], cwd=TF_DIR,
        capture_output=True, text=True, check=True,
    )
    value = result.stdout.strip()
    if not value or value.lower() in {"none", "null"}:
        raise ValueError(f"Terraform output is missing: {name}")
    return value


def build_payload(values: dict[str, str], script_bytes: bytes) -> dict[str, list[str]]:
    encoded = base64.b64encode(script_bytes).decode("ascii")
    commands = [
        "set -eu", "umask 077",
        "trap 'rm -f /tmp/opsflow-db-bootstrap.py /tmp/opsflow-db-bootstrap.b64' EXIT",
        "rm -f /tmp/opsflow-db-bootstrap.py /tmp/opsflow-db-bootstrap.b64",
    ]
    for start in range(0, len(encoded), 512):
        commands.append(
            "printf '%s' " + shlex.quote(encoded[start:start + 512])
            + " >> /tmp/opsflow-db-bootstrap.b64"
        )
    commands += [
        "base64 --decode /tmp/opsflow-db-bootstrap.b64 > /tmp/opsflow-db-bootstrap.py",
        "chmod 0700 /tmp/opsflow-db-bootstrap.py",
        "env " + " ".join(f"{key}={shlex.quote(value)}" for key, value in values.items())
        + " /usr/bin/python3 /tmp/opsflow-db-bootstrap.py",
    ]
    return {"commands": commands}


def main() -> None:
    mapping = {
        "AWS_REGION": "aws_region",
        "RDS_HOST": "live_rds_endpoint",
        "RDS_MASTER_SECRET_ARN": "live_rds_master_secret_arn",
        "CORE_DB_SECRET_ARN": "live_core_database_secret_arn",
        "INCIDENT_DB_SECRET_ARN": "live_incident_database_secret_arn",
    }
    values = {var: tf_output(name) for var, name in mapping.items()}
    values["RDS_HOST"] = values["RDS_HOST"].removesuffix(":5432")
    # Terraform's live_rds_endpoint is .address, not an arbitrary URI.
    if "//" in values["RDS_HOST"] or "/" in values["RDS_HOST"]:
        raise ValueError("Expected a plain RDS hostname from Terraform")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_payload(values, SCRIPT.read_bytes()), indent=2), encoding="utf-8")
    print(f"PASS: Non-secret SSM payload created: {OUT.relative_to(ROOT)}")
    print("PASS: No application passwords or RDS master password included")


if __name__ == "__main__":
    main()
