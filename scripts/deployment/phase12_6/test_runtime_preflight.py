"""Native-Windows-safe, side-effect-free tests for the runtime preflight."""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

BASE = pathlib.Path(__file__).resolve().parent


def load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load test subject: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pre = load("check_ec2_release.py", "check_ec2_release")
prepare = load("prepare_runtime_preflight_ssm.py", "prepare_runtime_preflight_ssm")


class RuntimePreflightTests(unittest.TestCase):
    def test_crlf_checksums_are_read_without_mutation(self):
        a = "a" * 64
        contents = (
            f"{a}  opsflow-source-abc.zip\r\n"
            f"{a}  opsflow-images-abc.tar.gz\r\n"
            f"{a}  receive_release.sh\r\n"
        ).encode("ascii")
        self.assertEqual(len(pre.checksum_entries(contents)), 3)
        self.assertIn(b"\r\n", contents)

    def test_reject_tricky_checksum_paths(self):
        data = ("a" * 64 + "  ../escape\n") * 3
        with self.assertRaises(pre.PreflightError):
            pre.checksum_entries(data.encode("ascii"))

    def test_secret_metadata_exact_and_never_prints_password(self):
        secret = {"engine": "postgres", "host": "example.rds.amazonaws.com", "port": 5432,
                  "username": "opsflow_core_login", "dbname": "opsflow", "password": "x" * 50}
        with mock.patch("builtins.print", side_effect=AssertionError("printed secrets")):
            pre.validate_secret(secret, "opsflow_core_login", "opsflow", "example.rds.amazonaws.com")
        with self.assertRaisesRegex(pre.PreflightError, "metadata"):
            pre.validate_secret(secret, "opsflow_incidents_login", "opsflow", "example.rds.amazonaws.com")
        with self.assertRaisesRegex(pre.PreflightError, "password"):
            pre.validate_secret({**secret, "password": "short"}, "opsflow_core_login", "opsflow", "example.rds.amazonaws.com")

    def test_expected_iam_role_required(self):
        pre.assert_expected_identity("arn:aws:sts::123456789012:assumed-role/opsflow-role/i-aaa", "opsflow-role")
        with self.assertRaises(pre.PreflightError):
            pre.assert_expected_identity("arn:aws:sts::123456789012:assumed-role/other/i-aaa", "opsflow-role")

    def test_generated_ssm_payload_never_contains_secret_value(self):
        values = {
            "AWS_REGION": "us-east-1", "RELEASE_TAG": "29b5857b88c0",
            "RDS_HOST": "test.example.rds.amazonaws.com", "EXPECTED_EC2_ROLE": "opsflow-role",
            "CORE_DB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:opsflow/core-AbC",
            "INCIDENT_DB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:opsflow/incident-AbC",
        }
        commands = prepare.build_commands(b"#!/usr/bin/env python3\nprint('PASS')\n", values)
        combined = "\n".join(commands)
        self.assertNotIn("DATABASE_URL=", combined)
        self.assertNotIn("--secret-string", combined)
        self.assertNotIn("get-secret-value", combined)
        self.assertIn("base64 --decode | python3 -", combined)
        with self.assertRaisesRegex(ValueError, "Invalid identifier"):
            prepare.build_commands(b"#!/usr/bin/env python3\n", {**values, "AWS_REGION": "region; rm -rf /"})

    def test_windows_offline_does_not_start_shell(self):
        with (mock.patch.object(sys, "platform", "win32"),
              mock.patch.object(pre.subprocess, "run", side_effect=AssertionError("Called subprocess")),
              mock.patch.object(pre.socket, "create_connection", side_effect=AssertionError("Called network"))):
            with self.assertRaisesRegex(pre.PreflightError, "Linux"):
                pre.main()


if __name__ == "__main__":
    unittest.main()
