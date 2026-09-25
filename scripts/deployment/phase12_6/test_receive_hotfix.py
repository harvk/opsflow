"""Portable regression tests for the staged-receiver checksum recovery.

Native Windows Python runs byte-level checks without invoking Git Bash.
Linux CI additionally executes the patched checksum verification in Bash.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

# Deployment utilities are standalone Python scripts, not a package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare_receive_ssm import build_commands  # noqa: E402
from receiver_patch import ANCHOR, patch_bytes  # noqa: E402


def checksum_fixture() -> tuple[dict[str, bytes], bytes]:
    contents = {
        "opsflow-source-abc.zip": b"source",
        "opsflow-images-abc.tar.gz": b"images",
        "receive_release.sh": ANCHOR,
    }
    manifest = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\r\n"
        for name, data in contents.items()
    ).encode("ascii")
    return contents, manifest


class ReceiverHotfixTests(unittest.TestCase):
    def test_only_one_checksum_line_is_patched(self) -> None:
        original = b"#!/usr/bin/env bash\nset -e\n(\n  cd /tmp\n" + ANCHOR + b")\necho done\n"
        replacement = (
            b"  tr -d '\\r' < SHA256SUMS > SHA256SUMS.lf\n"
            b"  sha256sum -c SHA256SUMS.lf\n"
        )
        patched = patch_bytes(original)
        self.assertEqual(original.count(ANCHOR), 1)
        self.assertIn(replacement, patched)
        self.assertEqual(patched.replace(replacement, ANCHOR, 1), original)

    def test_unknown_script_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_bytes(b"#!/bin/bash\nsha256sum -c other-file\n")
        with self.assertRaises(ValueError):
            patch_bytes(ANCHOR * 2)

    def test_crlf_manifest_is_normalized_for_patched_receiver(self) -> None:
        """Portable checks only; deliberately does not invoke a shell."""
        contents, raw = checksum_fixture()
        self.assertIn(b"\r\n", raw)
        normalized = raw.replace(b"\r\n", b"\n")
        self.assertNotIn(b"\r", normalized)
        self.assertEqual(normalized.count(b"\n"), 3)
        for line in normalized.splitlines():
            expected_hash, separator, name_bytes = line.partition(b"  ")
            self.assertEqual(separator, b"  ")
            name = name_bytes.decode("ascii")
            self.assertIn(name, contents)
            self.assertEqual(expected_hash.decode("ascii"), hashlib.sha256(contents[name]).hexdigest())

        sample = b"#!/usr/bin/env bash\nset -e\n(\n" + ANCHOR + b")\necho done\n"
        patched = patch_bytes(sample)
        self.assertIn(b"tr -d '\\r' < SHA256SUMS > SHA256SUMS.lf", patched)
        self.assertIn(b"sha256sum -c SHA256SUMS.lf", patched)

    def test_native_windows_does_not_launch_git_bash_or_create_tempdir(self) -> None:
        """Regression: native Windows Python must use the portable test path."""
        with (
            mock.patch.object(sys, "platform", "win32"),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("Windows spawned Bash")),
            mock.patch.object(tempfile, "TemporaryDirectory", side_effect=AssertionError("Windows created a temp directory")),
        ):
            self.test_crlf_manifest_is_normalized_for_patched_receiver()

    @unittest.skipUnless(
        sys.platform.startswith("linux"),
        "Shell integration runs only on Linux CI, never under native Windows Python",
    )
    def test_linux_shell_checksum_integration(self) -> None:
        if not all(shutil.which(binary) for binary in ("bash", "sha256sum", "tr")):
            self.skipTest("Linux shell tools unavailable")
        contents, raw = checksum_fixture()
        sample = b"#!/usr/bin/env bash\nset -e\n(\n" + ANCHOR + b")\necho done\n"
        with tempfile.TemporaryDirectory(prefix="opsflow-receiver-") as directory:
            root = pathlib.Path(directory)
            for name, data in contents.items():
                (root / name).write_bytes(data)
            (root / "SHA256SUMS").write_bytes(raw)
            script = root / "execution.sh"
            script.write_bytes(patch_bytes(sample))
            run = subprocess.run(
                ["bash", str(script)], cwd=root,
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            for name in contents:
                self.assertIn(f"{name}: OK", run.stdout)
            self.assertEqual((root / "SHA256SUMS").read_bytes(), raw)
            self.assertEqual((root / "SHA256SUMS.lf").read_bytes(), raw.replace(b"\r\n", b"\n"))

    def test_generated_commands_keep_s3_immutable(self) -> None:
        commands = build_commands(
            "us-east-1", "opsflow-test-release-bucket", "29b5857b88c0",
            "a" * 64, "b" * 64, "c2FtcGxl",
        )
        content = "\n".join(commands)
        self.assertIn("aws s3 cp", content)
        self.assertIn("base64 --decode | python3 -", content)
        self.assertIn("expected_patched", content)
        self.assertIn("tr -d", content)
        self.assertNotIn("aws s3 rm", content)
        self.assertNotIn("aws s3api put-object", content)
        self.assertNotIn("docker build", content)

    def test_invalid_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid"):
            build_commands("us-east-1;rm -rf /", "some-bucket", "29b5857b88c0", "a" * 64, "b" * 64, "c2FtcGxl")
        with self.assertRaisesRegex(ValueError, "Invalid"):
            build_commands("us-east-1", "bad bucket", "29b5857b88c0", "a" * 64, "b" * 64, "c2FtcGxl")


if __name__ == "__main__":
    unittest.main()
