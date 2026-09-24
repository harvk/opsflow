# cspell:words opsflow
"""Produce an OpsFlow release from *committed* source, not working files.

Windows Git Bash:
  backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_release_bundle.py --source-only
  backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_release_bundle.py --build-images

Offline validation is intentionally separated from running Docker builds.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SELECTION = ("backend", "incident-service", "frontend", "contracts", "compose.production.yaml")
IMAGE_PREFIXES = ("opsflow-backend", "opsflow-incident-service", "opsflow-frontend")
BANNED = re.compile(
    r"(^|/)(\.env(\.(?!example$|docker\.example$)[^/]*)?$|\.aws|\.opsflow-secrets)(/|$)|"
    r"\.(pem|p12|pfx|tfstate|key)$|(^|/)terraform\.tfstate(\.|$)",
    re.IGNORECASE,
)


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> str:
    result = subprocess.run(list(args), cwd=cwd, text=True, check=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def inspect_names(names: list[str]) -> None:
    flagged = [name for name in names if BANNED.search(name.replace("\\", "/"))]
    if flagged:
        raise RuntimeError("STOP: Sensitive filenames in release selection: " + repr(flagged))
    required = {"backend/Dockerfile", "incident-service/Dockerfile", "frontend/Dockerfile",
                "frontend/nginx/production.conf", "compose.production.yaml"}
    absent = required - set(names)
    if absent:
        raise RuntimeError("STOP: Missing required tracked files: " + repr(sorted(absent)))


def get_release(repo: Path, out: Path) -> tuple[str, str, Path]:
    branch = run("git", "branch", "--show-current", cwd=repo, capture=True)
    if branch != "feature/live-deploy":
        raise RuntimeError(f"STOP: Branch is {branch!r}, expected feature/live-deploy")
    if run("git", "status", "--porcelain", cwd=repo, capture=True):
        raise RuntimeError("STOP: Git working tree is not clean; review and commit first")
    commit = run("git", "rev-parse", "HEAD", cwd=repo, capture=True)
    tag = commit[:12]
    listed = run("git", "ls-files", "--", *SELECTION, cwd=repo, capture=True).splitlines()
    inspect_names(listed)
    out.mkdir(parents=True, exist_ok=True)
    final_archive = out / f"opsflow-source-{tag}.zip"
    with tempfile.TemporaryDirectory(prefix="opsflow-archive-", dir=out) as t:
        candidate = Path(t) / "source.zip"
        run("git", "archive", "--format=zip", f"--output={candidate}", "HEAD", *SELECTION, cwd=repo)
        with zipfile.ZipFile(candidate) as zf:
            if zf.testzip() is not None:
                raise RuntimeError("STOP: Generated source archive is corrupt")
            inspect_names(zf.namelist())
        if final_archive.exists():
            if digest(final_archive) != digest(candidate):
                raise RuntimeError(f"STOP: Existing archive differs: {final_archive}; do not overwrite")
        else:
            shutil.copyfile(candidate, final_archive)
    return commit, tag, final_archive


def build_images(repo: Path, out: Path, tag: str, archive: Path) -> Path:
    output = out / f"opsflow-images-{tag}.tar.gz"
    if output.exists():
        raise RuntimeError(f"STOP: Existing image archive {output}; inspect before rebuilding")
    if shutil.which("docker") is None:
        raise RuntimeError("STOP: Docker CLI not found")
    with tempfile.TemporaryDirectory(prefix="opsflow-build-", dir=out) as build_dir:
        src = Path(build_dir)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(src)
        for name, directory, args in (
            ("opsflow-backend", "backend", ["--build-arg", "PYTHON_VERSION=3.13.15"]),
            ("opsflow-incident-service", "incident-service", ["--build-arg", "PYTHON_VERSION=3.13.15"]),
            ("opsflow-frontend", "frontend", ["--build-arg", "NODE_VERSION=24",
                                                  "--build-arg", "VITE_API_BASE_URL=/api/v1",
                                                  "--build-arg", "VITE_CSRF_COOKIE_NAME=opsflow_csrf",
                                                  "--build-arg", "NGINX_SITE_CONF=nginx/production.conf"]),
        ):
            run("docker", "build", "--platform", "linux/amd64", *args,
                "-t", f"{name}:{tag}", str(src / directory), cwd=repo)
            inspected = run("docker", "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}",
                            f"{name}:{tag}", cwd=repo, capture=True)
            if inspected != "linux/amd64":
                raise RuntimeError(f"STOP: Unexpected image architecture: {name}={inspected}")
        names = [f"{prefix}:{tag}" for prefix in IMAGE_PREFIXES]
        with output.open("wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=1) as zipped:
                with subprocess.Popen(["docker", "save", *names], cwd=repo, stdout=subprocess.PIPE) as proc:
                    stdout = proc.stdout
                    if stdout is None:
                        raise RuntimeError("STOP: docker save did not provide an output stream")
                    while True:
                        block = stdout.read(1024 * 1024)
                        if not block:
                            break
                        zipped.write(block)
                    if proc.wait() != 0:
                        raise RuntimeError("STOP: docker save failed")
    if output.stat().st_size == 0:
        raise RuntimeError("STOP: Empty Docker image archive")
    return output


def finish(out: Path, commit: str, tag: str, source: Path, images: Path, receiver: Path) -> None:
    manifest = out / "release.json"
    checksums = out / "SHA256SUMS"
    if manifest.exists() or checksums.exists():
        raise RuntimeError("STOP: Existing release manifest; inspect before running again")
    info = {}
    for artifact in (source, images, receiver):
        info[artifact.name] = {"sha256": digest(artifact), "bytes": artifact.stat().st_size}
    payload = {"commit": commit, "tag": tag, "platform": "linux/amd64", "files": info,
               "images": [f"{name}:{tag}" for name in IMAGE_PREFIXES]}
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    checksums.write_text("".join(f"{info[item.name]['sha256']}  {item.name}\n"
                                  for item in (source, images, receiver)), encoding="ascii", newline="\n")
    print("PASS: Release bundle built. SHA256SUMS:")
    print(checksums.read_text(encoding="ascii"))


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--source-only", action="store_true")
    mode.add_argument("--build-images", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    out = repo / ".opsflow-migration" / "phase12-6d"
    try:
        commit, tag, source = get_release(repo, out)
        if args.source_only:
            print(f"PASS: Verified committed source archive: {source}")
            print(f"RELEASE_TAG={tag}")
            print(f"SHA256={digest(source)}")
        else:
            receiver = repo / "scripts/deployment/phase12_6/receive_release.sh"
            if not receiver.is_file():
                raise RuntimeError(f"STOP: Missing receiver: {receiver}")
            images = build_images(repo, out, tag, source)
            finish(out, commit, tag, source, images, receiver)
    except (RuntimeError, subprocess.CalledProcessError, OSError, zipfile.BadZipFile) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
