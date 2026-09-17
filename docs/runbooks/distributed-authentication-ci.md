# Distributed Authentication CI Gates

This runbook describes the automated quality and deployment
checks for OpsFlow's bidirectional service authentication.

The Core Backend and Incident Service use separate RSA key
pairs. Each service signs short-lived JWTs with its own private
key and verifies the other service with that service's public
key. The retired shared token is not a supported authentication
path.

## CI workflow

The workflow is located at:

```text
.github/workflows/opsflow-quality.yml
```

The workflow runs on pushes to `main` and
`feature/distributed-authentication`, pull requests, and manual
dispatches.

## Quality gates

The `whitespace` job checks:

- repository trailing whitespace;
- Git whitespace errors;
- absence of retired shared-token identifiers in production
  application and deployment paths.

The `backend` and `incident-service` jobs each:

- install the checked-in runtime and development dependency
  manifests;
- migrate an isolated PostgreSQL test database;
- run Ruff;
- run focused service-identity, adversarial, security-event,
  and metrics tests;
- run the complete service test suite.

The Backend job also validates both RSA key generators and
their expected output filenames.

## Compose deployment gate

The `compose-smoke` job runs only after whitespace, Backend,
Incident Service, and frontend jobs succeed. It:

1. creates CI-only environment files;
2. generates ephemeral Core and Incident RSA keypairs;
3. renders and validates the Compose configuration;
4. validates static secret mounts and key-path settings;
5. builds the runtime images;
6. starts the stack and waits for container health;
7. verifies runtime key isolation inside both services;
8. sends a Core-signed request to Incident Service;
9. sends an Incident-signed request to Core Backend;
10. reports logs on failure and always removes the CI stack.

The expected runtime boundary is:

| Service | Private signing key | Public verification key |
|---|---|---|
| Core Backend | Core | Incident Service |
| Incident Service | Incident Service | Core |

Neither service may receive the other service's private key.

## Local static validation

Run from the repository root in Windows Git Bash:

```bash
py -3 scripts/check_distributed_auth_contract.py

py -3 scripts/validate_service_identity_compose.py \
  --env-file .env.docker

py -3 scripts/trim_trailing_whitespace.py --check

git diff --check
```

Expected contract results:

```text
Distributed-authentication production contract passed.
Service-identity Compose key boundaries passed.
```

## Local service validation

```bash
(
  cd backend &&
  ./.venv/Scripts/python.exe -m ruff check app tests &&
  ./.venv/Scripts/python.exe -m pytest -q
)

(
  cd incident-service &&
  ./.venv/Scripts/python.exe -m ruff check app tests &&
  ./.venv/Scripts/python.exe -m pytest -q
)
```

## Local Compose validation

Docker Desktop must be running.

```bash
docker compose --env-file .env.docker config --quiet

docker compose --env-file .env.docker up \
  --detach \
  --build \
  --wait

docker compose --env-file .env.docker ps --all
```

The persistent services must be healthy. Migration and
provisioning containers must exit with code zero. Incident
Service must remain private to the Compose network.

## Failure interpretation

| Failure | Meaning |
|---|---|
| Production contract | A retired shared-token identifier returned to production code or configuration |
| Compose boundary | A required secret, mount, or `/run/secrets` path changed |
| Focused security tests | JWT verification, authorization, observability, or adversarial rejection regressed |
| Runtime isolation | A container received a missing or unauthorized identity key |
| Bidirectional request | Signing, verification, audience, scope, routing, or key distribution failed |

CI keys are ephemeral test credentials. Production credentials
must be provisioned through the deployment platform's secret
management system and must never be committed to Git.
