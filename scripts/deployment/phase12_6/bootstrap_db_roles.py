#!/usr/bin/env python3
"""One-time EC2 bootstrap: AWS-generated-in-process restricted PG logins.

Requires only the EC2 instance profile, installed AWS CLI, Docker and Python3.
Secrets remain in process memory and an ephemeral /dev/shm directory.
No passwords are printed or supplied as shell/SSM command arguments.
"""
# cspell:ignore geteuid
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

IMAGE = "postgres:18.6-bookworm"
RUNTIME = (
    ("CORE_DB_SECRET_ARN", "opsflow_core_login", "opsflow", "opsflow_app"),
    ("INCIDENT_DB_SECRET_ARN", "opsflow_incidents_login", "opsflow_incidents", "opsflow_incidents_app"),
)
ROOT = Path("/opt/opsflow")
STARTED = ROOT / ".phase12-6b-started"
COMPLETE = ROOT / ".phase12-6b-verified"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value or value.lower() in {"none", "null"} or value.startswith("YOUR_"):
        raise RuntimeError(f"Required identifier not configured: {name}")
    return value


def aws(region: str, *args: str) -> str:
    p = subprocess.run(
        ["aws", *args, "--region", region, "--output", "text"],
        text=True, capture_output=True, check=False,
    )
    if p.returncode:
        # Never log sensitive stdout. AWS errors omit secret values; report only
        # a short non-sensitive action label and stderr for troubleshooting.
        raise RuntimeError(f"AWS operation {args[0]} {args[1]} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def pgpass_field(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("\n", "")


def sql_string(value: str) -> str:
    if "\x00" in value:
        raise ValueError("SQL string contains NUL")
    return "'" + value.replace("'", "''") + "'"


def write_private(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def pg_cmd(workdir: Path, host: str, user: str, db: str, passfile: str) -> list[str]:
    return [
        "docker", "run", "--rm", "-i", "--network", "host",
        "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
        "--mount", f"type=bind,source={workdir},target=/run/opsflow-db,readonly",
        "--env", f"PGPASSFILE=/run/opsflow-db/{passfile}",
        "--env", "PGSSLMODE=verify-full",
        "--env", "PGSSLROOTCERT=/run/opsflow-db/global-bundle.pem",
        "--env", "PGCONNECT_TIMEOUT=10",
        IMAGE,
        "psql", "-X", "--no-psqlrc", "--set=ON_ERROR_STOP=1", "--quiet",
        "--no-align", "--tuples-only", "--host", host, "--port", "5432",
        "--username", user, "--dbname", db,
    ]


def sql(workdir: Path, host: str, user: str, db: str, passfile: str,
        statement: str, *, show: bool = False, expect_failure: bool = False, sensitive: bool = False) -> str:
    p = subprocess.run(
        pg_cmd(workdir, host, user, db, passfile),
        input=statement, text=True, capture_output=True, check=False,
    )
    if expect_failure:
        if p.returncode == 0:
            raise RuntimeError("Database isolation failure: unintended connection succeeded")
        return ""
    if p.returncode:
        # Never echo the SQL input: initial role creation contains passwords.
        if sensitive:
            raise RuntimeError("Sensitive role DDL failed; database password SQL and stderr suppressed. "
                               "Inspect connectivity and the first non-secret preflight results.")
        raise RuntimeError(f"PostgreSQL operation failed: {p.stderr.strip()}")
    if show:
        return p.stdout.strip()
    return ""


def get_runtime_secret(region: str, arn: str, username: str, dbname: str,
                       host: str, workdir: Path, shortname: str) -> dict[str, str]:
    versions = aws(region, "secretsmanager", "list-secret-version-ids", "--secret-id", arn,
                   "--query", "Versions[?contains(VersionStages, 'AWSCURRENT')].VersionId")
    if versions and versions != "None":
        raw = aws(region, "secretsmanager", "get-secret-value", "--secret-id", arn,
                  "--query", "SecretString")
        data = json.loads(raw)
        if not isinstance(data, dict) or any(data.get(k) != v for k, v in (
            ("username", username), ("dbname", dbname), ("host", host), ("engine", "postgres"))):
            raise RuntimeError(f"Existing {shortname} secret metadata does not match this deployment; stop")
        if not isinstance(data.get("password"), str) or len(data["password"]) < 32:
            raise RuntimeError(f"Existing {shortname} secret password is missing or weak; stop")
        print(f"PASS: Reusing existing {shortname} secret version (no rotation)")
        return data

    data = {
        "engine": "postgres", "host": host, "port": 5432,
        "username": username, "password": secrets.token_urlsafe(48), "dbname": dbname,
    }
    path = workdir / f"{shortname}.json"
    write_private(path, json.dumps(data, separators=(",", ":")))
    try:
        aws(region, "secretsmanager", "put-secret-value", "--secret-id", arn,
            "--secret-string", f"file://{path}", "--query", "VersionId")
    finally:
        path.unlink(missing_ok=True)
    print(f"PASS: Generated and stored {shortname} login secret inside AWS")
    return data


def main() -> int:
    # This script is developed on Windows but executed on Amazon Linux EC2.
    # Windows Python typing does not expose the POSIX-only os.geteuid attribute.
    if sys.platform != "linux":
        raise RuntimeError("Run this script on the Linux EC2 instance through SSM")
    get_effective_uid = getattr(os, "geteuid", None)
    if not callable(get_effective_uid) or get_effective_uid() != 0:
        raise RuntimeError("Run via SSM AWS-RunShellScript as root")
    for tool in ("aws", "docker"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"Missing EC2 prerequisite: {tool}")
    region = required("AWS_REGION")
    host = required("RDS_HOST")
    master_arn = required("RDS_MASTER_SECRET_ARN")
    for key, *_ in RUNTIME:
        required(key)
    if COMPLETE.exists():
        print("PASS: Bootstrap already verified; will not rotate existing logins")
        return 0
    if not Path("/dev/shm").is_dir():
        raise RuntimeError("Required ephemeral secret filesystem /dev/shm is unavailable")
    ROOT.mkdir(mode=0o750, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="opsflow-db-", dir="/dev/shm") as dirname:
        workdir = Path(dirname)
        workdir.chmod(0o700)
        ca_path = workdir / "global-bundle.pem"
        with urllib.request.urlopen(
            "https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem", timeout=35
        ) as response:
            ca_path.write_bytes(response.read(1024 * 1024))
        ca_path.chmod(0o600)
        if ca_path.stat().st_size < 1024:
            raise RuntimeError("Downloaded RDS CA certificate bundle is unexpectedly small")

        master = json.loads(aws(region, "secretsmanager", "get-secret-value",
                               "--secret-id", master_arn, "--query", "SecretString"))
        master_user = master.get("username", "")
        master_password = master.get("password", "")
        if not master_user or not master_password:
            raise RuntimeError("RDS-managed master secret is missing username/password")
        write_private(workdir / "master.pgpass", ":".join([
            pgpass_field(host), "5432", "*", pgpass_field(master_user),
            pgpass_field(master_password),
        ]) + "\n")
        del master, master_password
        existing_state = sql(workdir, host, master_user, "postgres", "master.pgpass",
                       "SELECT rolname || '|' || CASE WHEN rolcanlogin THEN 't' ELSE 'f' END FROM pg_roles WHERE rolname IN "
                       "('opsflow_app','opsflow_incidents_app','opsflow_core_login',"
                       "'opsflow_incidents_login') ORDER BY rolname;", show=True).splitlines()
        existing = {row.split("|")[0]: row.split("|")[1] for row in existing_state}
        expected = {"opsflow_app", "opsflow_incidents_app"}
        if not expected.issubset(set(existing)) or any(existing[r] != "f" for r in expected):
            raise RuntimeError("Phase 12.5 NOLOGIN privilege roles missing: stop")
        login_existing = {"opsflow_core_login", "opsflow_incidents_login"} & set(existing)
        if login_existing and not STARTED.exists():
            raise RuntimeError("Existing login roles predate this bootstrap: manual audit required")
        STARTED.touch(mode=0o600, exist_ok=True)
        runtime: list[tuple[dict[str, str], str]] = []
        for key, username, dbname, group in RUNTIME:
            secret_data = get_runtime_secret(region, required(key), username, dbname,
                                             host, workdir, username)
            runtime.append((secret_data, group))
        statements = ["BEGIN;"]
        for data, group in runtime:
            username, pwd = data["username"], data["password"]
            if username not in login_existing:
                statements.append(f"CREATE ROLE {username} LOGIN INHERIT NOSUPERUSER "
                                  f"NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {sql_string(pwd)};")
            else:
                statements.append(f"ALTER ROLE {username} LOGIN INHERIT NOSUPERUSER "
                                  f"NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {sql_string(pwd)};")
            statements.append(f"GRANT {group} TO {username} WITH INHERIT TRUE, SET FALSE;")
        # PostgreSQL grants database CONNECT to PUBLIC by default; without
        # this revoke, the other service's login could reach the wrong DB.
        statements.extend([
            "REVOKE CONNECT ON DATABASE opsflow FROM PUBLIC;",
            "REVOKE CONNECT ON DATABASE opsflow_incidents FROM PUBLIC;",
            "COMMIT;",
        ])
        sql(workdir, host, master_user, "postgres", "master.pgpass", "\n".join(statements), sensitive=True)
        print("PASS: Isolated, non-superuser database logins created / reconciled")
        for data, group in runtime:
            name = data["username"]
            pgpass = f"{name}.pgpass"
            write_private(workdir / pgpass, ":".join([
                pgpass_field(host), "5432", "*", pgpass_field(name),
                pgpass_field(data["password"]),
            ]) + "\n")
            result = sql(workdir, host, name, data["dbname"], pgpass,
                         "SELECT current_user, "
                         f"pg_has_role(current_user,{sql_string(group)},'USAGE'),"
                         "has_schema_privilege(current_user,'public','USAGE');", show=True)
            if result.strip() != f"{name}|t|t":
                raise RuntimeError(f"Runtime database login/role verification failed: {name}")
            wrong_db = "opsflow_incidents" if data["dbname"] == "opsflow" else "opsflow"
            sql(workdir, host, name, wrong_db, pgpass, "SELECT 1;", expect_failure=True)
            print(f"PASS: {name} can authenticate to its database but not the other one")

        role_checks = sql(workdir, host, master_user, "postgres", "master.pgpass",
                          "SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolreplication "
                          "FROM pg_roles WHERE rolname IN "
                          "('opsflow_core_login','opsflow_incidents_login') ORDER BY rolname;", show=True)
        for line in role_checks.splitlines():
            if line.split("|")[1:] != ["f", "f", "f", "f"]:
                raise RuntimeError("Unexpected privileged runtime database role: stop")
        if len(role_checks.splitlines()) != 2:
            raise RuntimeError("Missing one or more runtime database roles")
        COMPLETE.touch(mode=0o600, exist_ok=True)
        print("PASS: 12.6B database bootstrap verified; no secret value printed")
        print("NEXT: remove the temporary master-secret IAM policy via Terraform")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Avoid printing secret data; SQL text is never included in raised error.
        print(f"STOP: {exc}", file=sys.stderr)
        sys.exit(1)
