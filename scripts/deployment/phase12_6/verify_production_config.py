"""Read-only structural validation of OpsFlow production configuration.

No credentials, Docker daemon, AWS identity, or populated runtime files needed.
Run from the OpsFlow repository root on Windows or Linux.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys

import yaml


def validate(repo: Path) -> None:
    compose = yaml.safe_load((repo / "compose.production.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    required = {"backend", "incident-service", "frontend", "incident-reconciler", "incident-outbox-relay", "incident-completion-outbox-relay"}
    assert required == set(services), f"Unexpected service set: {set(services) ^ required}"
    assert not ({"db", "migrate", "incident-migrate", "provision-databases"} & services.keys())
    assert set(services["frontend"]["networks"]) == {"opsflow_edge"}
    assert set(services["backend"]["networks"]) == {"opsflow_edge", "opsflow_services"}
    assert set(services["incident-service"]["networks"]) == {"opsflow_services"}
    assert "ports" not in services["backend"] and "ports" not in services["incident-service"]
    assert all(p.startswith('127.0.0.1:') for p in services["frontend"]["ports"])
    for name in required - {"frontend"}:
        assert services[name]["environment"].get("AWS_EC2_METADATA_DISABLED") != "true"
    for name in ("incident-reconciler", "incident-outbox-relay", "incident-completion-outbox-relay"):
        assert services[name]["profiles"] == ["workers"]
    assert services["backend"]["environment"]["INCIDENT_GATEWAY_MODE"] == "http"
    assert services["frontend"]["build"]["args"]["VITE_API_BASE_URL"] == "/api/v1"
    assert set(services["backend"]["secrets"]) == {"core_service_identity_private_key", "incident_service_identity_public_key"}
    assert set(services["incident-service"]["secrets"]) == {"core_service_identity_public_key", "incident_service_identity_private_key"}
    assert "env_file" not in services["frontend"]
    assert ".env.docker" not in (repo / "compose.production.yaml").read_text(encoding="utf-8")
    assert ".aws" not in (repo / "compose.production.yaml").read_text(encoding="utf-8")

    nginx = (repo / "frontend/nginx/production.conf").read_text(encoding="utf-8")
    assert "location /api/" in nginx
    assert "proxy_pass http://backend:8000;" in nginx
    assert "location = /healthz" in nginx
    dockerfile = (repo / "frontend/Dockerfile").read_text(encoding="utf-8")
    assert "ARG NGINX_SITE_CONF=nginx/default.conf" in dockerfile
    assert "COPY ${NGINX_SITE_CONF}" in dockerfile
    config = (repo / "backend/app/core/config.py").read_text(encoding="utf-8")
    ast.parse(config)
    assert 'test_database_url: str = ""' in config
    assert "database_url: str" in config
    for name in ("backend", "incident-service"):
        assert "postgres" not in services[name].get("depends_on", {}), name

    print("PASS: only intended production services; no local PostgreSQL or migration container")
    print("PASS: internal-only backend/incident and loopback-only pre-ALB frontend")
    print("PASS: separate service-identity key grants and optional worker profile")
    print("PASS: production NGINX same-origin API routing and backend optional TEST_DATABASE_URL")
    print("PASS: no local AWS credential mounts")


if __name__ == "__main__":
    try:
        validate(Path.cwd())
    except (AssertionError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
