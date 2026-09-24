# cspell:words opsflow
"""Offline regression tests for release creation and SSM receiver generation.

These tests never access AWS, invoke Docker, or launch Bash on Windows.
The Linux receiver shell-integration test lives in test_receive_hotfix.py.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BASE = pathlib.Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load deployment module: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("verify_release_plan")
prepare = load("prepare_release_bundle")
receive = load("prepare_receive_ssm")


class TransferTests(unittest.TestCase):
    def test_create_and_cleanup_plan(self) -> None:
        for mode, action in (("create", "create"), ("cleanup", "delete")):
            plan = {"resource_changes": [
                {"address": address, "mode": "managed", "change": {"actions": [action]}}
                for address in verify.EXPECTED
            ]}
            ok, message = verify.validate(plan, mode)
            self.assertTrue(ok, message)

    def test_plan_rejects_unrelated_ec2_change(self) -> None:
        plan = {"resource_changes": [
            {"address": address, "mode": "managed", "change": {"actions": ["create"]}}
            for address in verify.EXPECTED
        ] + [{"address": "aws_instance.live_ec2", "mode": "managed", "change": {"actions": ["update"]}}]}
        self.assertFalse(verify.validate(plan, "create")[0])

    def test_secret_filename_filter(self) -> None:
        for path in ("backend/.env", "backend/key.pem", "frontend/.aws/credentials"):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                prepare.inspect_names([path, "frontend/Dockerfile"])
        prepare.inspect_names([
            "backend/Dockerfile", "incident-service/Dockerfile",
            "frontend/Dockerfile", "frontend/nginx/production.conf",
            "compose.production.yaml", "backend/.env.example",
        ])

    def test_receiver_builder_contract_requires_verified_patch(self) -> None:
        # Catches helper API changes explicitly; the previous test called an
        # obsolete three-argument signature and failed before testing anything.
        self.assertEqual(list(inspect.signature(receive.build_commands).parameters), [
            "region", "bucket", "tag", "original_sha", "patched_sha", "encoded_patch",
        ])

    def test_receiver_command_handles_crlf_and_preserves_s3_release(self) -> None:
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("Unexpected process")):
            commands = receive.build_commands(
                "us-east-1", "opsflow-test-bucket", "0123456789ab",
                "a" * 64, "b" * 64, "c2FtcGxl",
            )
        full = "\n".join(commands)
        self.assertIn("tr -d '\\r'", full)
        self.assertIn('expected_list=$(tr -d', full)
        self.assertIn('expected_original=', full)
        self.assertIn('expected_patched=', full)
        self.assertIn('actual_patched=', full)
        self.assertIn('base64 --decode | python3 -', full)
        self.assertIn('bash /tmp/opsflow-receiver-execution.sh', full)
        self.assertNotIn('aws s3 rm', full)
        self.assertNotIn('aws s3api put-object', full)
        self.assertNotIn('docker build', full)
        # This assertion is byte-based and platform-independent: no Git Bash
        # subprocess is launched from native Windows Python.
        sample = ("a" * 64 + "  receive_release.sh\r\n").encode("ascii")
        self.assertEqual(sample.replace(b"\r", b"").split(b"  ", 1)[1], b"receive_release.sh\n")

    def test_receiver_rejects_invalid_patch_metadata(self) -> None:
        correct = ("us-east-1", "opsflow-test-bucket", "0123456789ab", "a" * 64, "b" * 64, "c2FtcGxl")
        for index, invalid in ((0, "us-east-1;rm"), (1, "bad bucket"), (2, "wrong-tag"),
                               (3, "not-a-hash"), (4, "not-a-hash"), (5, "invalid payload !")):
            values = list(correct)
            values[index] = invalid
            with self.subTest(index=index), self.assertRaises(ValueError):
                receive.build_commands(*values)

    def test_release_checksum_list_uses_lf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="opsflow-release-test-") as directory:
            root = pathlib.Path(directory)
            source, images, receiver = (
                root / "source.zip", root / "images.tar.gz", root / "receiver.sh",
            )
            for path in (source, images, receiver):
                path.write_bytes(b"test artifact")
            prepare.finish(root, "0" * 40, "0" * 12, source, images, receiver)
            content = (root / "SHA256SUMS").read_bytes()
            self.assertNotIn(b"\r", content)
            self.assertEqual(content.count(b"\n"), 3)
            for line in content.splitlines():
                checksum, separator, filename = line.partition(b"  ")
                self.assertEqual(separator, b"  ")
                self.assertEqual(checksum.decode("ascii"), hashlib.sha256((root / filename.decode("ascii")).read_bytes()).hexdigest())

    def test_source_archive_from_clean_git(self) -> None:
        with tempfile.TemporaryDirectory(prefix="opsflow-release-git-") as directory:
            root = pathlib.Path(directory)
            subprocess.run(["git", "init", "-q", "-b", "feature/live-deploy"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "unit@test.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Unit Test"], cwd=root, check=True)
            for rel in (
                "backend/Dockerfile", "incident-service/Dockerfile", "frontend/Dockerfile",
                "frontend/nginx/production.conf", "contracts/README", "compose.production.yaml",
            ):
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            commit, tag, archive = prepare.get_release(root, root / ".opsflow-migration/release")
            self.assertEqual(tag, commit[:12])
            self.assertTrue(archive.is_file())
            (root / "backend/Dockerfile").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                prepare.get_release(root, root / ".opsflow-migration/release")


if __name__ == "__main__":
    unittest.main()
