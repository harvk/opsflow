"""Offline guards for the release process. No AWS or Docker required."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

BASE = pathlib.Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("verify_release_plan")
prepare = load("prepare_release_bundle")


class TransferTests(unittest.TestCase):
    def test_create_and_cleanup_plan(self):
        for operation in ("create", "cleanup"):
            plan = {"resource_changes": [
                {"address": key, "mode": "managed", "change": {"actions": [operation if operation == "create" else "delete"]}}
                for key in verify.EXPECTED
            ]}
            self.assertTrue(verify.validate(plan, operation)[0])

    def test_plan_rejects_unrelated_ec2_change(self):
        plan = {"resource_changes": [
            {"address": key, "mode": "managed", "change": {"actions": ["create"]}}
            for key in verify.EXPECTED
        ] + [{"address": "aws_instance.live_ec2", "mode": "managed", "change": {"actions": ["update"]}}]}
        self.assertFalse(verify.validate(plan, "create")[0])

    def test_secret_filename_filter(self):
        with self.assertRaises(RuntimeError):
            prepare.inspect_names(["backend/.env", "frontend/Dockerfile"])
        with self.assertRaises(RuntimeError):
            prepare.inspect_names(["backend/key.pem", "frontend/Dockerfile"])
        prepare.inspect_names(["backend/Dockerfile", "incident-service/Dockerfile",
                               "frontend/Dockerfile", "frontend/nginx/production.conf",
                               "compose.production.yaml", "backend/.env.example"])

    def test_source_archive_from_clean_git(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            subprocess.run(["git", "init", "-q", "-b", "feature/live-deploy"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "unit@test.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Unit Test"], cwd=root, check=True)
            for rel in ["backend/Dockerfile", "incident-service/Dockerfile", "frontend/Dockerfile",
                        "frontend/nginx/production.conf", "contracts/README", "compose.production.yaml"]:
                p = root / rel
                p.parent.mkdir(exist_ok=True, parents=True)
                p.write_text("fixture\n")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            commit, tag, archive = prepare.get_release(root, root / ".opsflow-migration/release")
            self.assertEqual(commit[:12], tag)
            self.assertTrue(archive.is_file())
            # Working source changes MUST stop bundling rather than leak in.
            (root / "backend/Dockerfile").write_text("changed\n")
            with self.assertRaises(RuntimeError):
                prepare.get_release(root, root / ".opsflow-migration/release")


if __name__ == "__main__":
    unittest.main()
