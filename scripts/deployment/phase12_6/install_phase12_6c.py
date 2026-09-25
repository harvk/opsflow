"""Safely install Phase 12.6C source-reviewed files in an existing checkout.

Run from repository root with the Windows backend virtualenv interpreter.
The uploaded source inventory is a point-in-time snapshot. We refuse to
replace evolved application files when their bytes differ from that snapshot.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIGESTS = PACKAGE_ROOT / "scripts/deployment/phase12_6/source_sha256.json"
REPLACED = ("backend/app/core/config.py", "frontend/Dockerfile")
NEW = (
    "compose.production.yaml",
    "frontend/nginx/production.conf",
    ".env.production.example",
    "scripts/deployment/phase12_6/verify_production_config.py",
    "scripts/deployment/phase12_6/test_production_config.py",
    "scripts/deployment/phase12_6/source_sha256.json",
    "scripts/deployment/phase12_6/install_phase12_6c.py",
    "PHASE_12_6C_README.md",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    repo = Path.cwd().resolve()
    if not (repo / "compose.yaml").is_file() or not (repo / "backend/app/core/config.py").is_file():
        raise RuntimeError("Run this script from your OpsFlow repository ROOT, not Terraform or EC2")
    expected = json.loads(SOURCE_DIGESTS.read_text(encoding="utf-8"))
    changes: list[tuple[Path, Path]] = []

    for relative in REPLACED:
        source = PACKAGE_ROOT / relative
        target = repo / relative
        if not target.is_file():
            raise RuntimeError(f"Missing expected application source: {relative}")
        actual = sha256(target)
        wanted = expected[relative]
        if actual == sha256(source):
            print(f"UNCHANGED: Desired 12.6C version already installed: {relative}")
        elif actual == wanted:
            changes.append((source, target))
        else:
            raise RuntimeError(
                f"SAFETY STOP: {relative} differs from the uploaded source version. "
                "Do not overwrite newer code; share its current contents to reconcile."
            )

    for relative in NEW:
        source = PACKAGE_ROOT / relative
        target = repo / relative
        if target.exists() and sha256(target) != sha256(source):
            raise RuntimeError(
                f"SAFETY STOP: {relative} exists with different contents. Review before replacement."
            )
        if not target.exists():
            changes.append((source, target))

    for source, target in changes:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"INSTALLED: {target.relative_to(repo)}")

    print("PASS: Phase 12.6C files installed without overwriting unverified application changes")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
