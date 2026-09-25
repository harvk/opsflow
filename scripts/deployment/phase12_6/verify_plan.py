#!/usr/bin/env python3
"""Verify only the intended Phase 12.6B Terraform operations occur.

Usage in infrastructure/terraform (Git Bash):
  terraform show -json phase-12-6b.tfplan | \
    ../../backend/.venv/Scripts/python.exe ../../scripts/deployment/phase12_6/verify_plan.py create
Or for cleanup plan: ... verify_plan.py cleanup
"""
from __future__ import annotations

import json
import sys

PERMANENT = {
    "aws_secretsmanager_secret.live_core_db_login",
    "aws_secretsmanager_secret.live_incident_db_login",
    "aws_iam_role_policy.live_runtime_db_secret_read",
}
TEMPORARY = "aws_iam_role_policy.live_db_bootstrap_temp"


def verify(plan: dict, mode: str) -> None:
    if mode not in {"create", "cleanup"}:
        raise ValueError("Specify create or cleanup")
    want = {addr: ("create" if mode == "create" else "delete")
            for addr in ((PERMANENT | {TEMPORARY}) if mode == "create" else {TEMPORARY})}
    actual = {}
    for change in plan.get("resource_changes", []):
        if change.get("mode") != "managed":
            continue
        actions = change.get("change", {}).get("actions", [])
        if actions == ["no-op"]:
            continue
        actual[change["address"]] = ",".join(actions)
    if actual != want:
        raise ValueError(f"Unexpected Terraform changes. Expected {want}; actual {actual}")
    print(f"PASS: Phase 12.6B {mode} plan contains exactly the intended changes")
    print("PASS: Existing EC2, RDS, networking and serverless resources remain untouched")


if __name__ == "__main__":
    try:
        verify(json.load(sys.stdin), sys.argv[1] if len(sys.argv) > 1 else "")
    except (ValueError, json.JSONDecodeError) as error:
        print(f"STOP: {error}", file=sys.stderr)
        sys.exit(1)
