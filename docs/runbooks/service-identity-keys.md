# Service Identity Key Provisioning

This runbook provisions and validates the local-development
RSA key pairs used for bidirectional OpsFlow service identity.

The Core Backend signs short-lived service JWTs with the
private key. The Incident Service verifies those JWTs with
the matching public key. The Incident Service owns a separate
private key for tokens sent to Core, and Core receives only
that identity's public key.

This procedure does not provision production credentials.
Production deployments must use the secret-management and
workload-identity facilities of the selected platform.

## Security boundary

| Component | Core private | Core public | Incident private | Incident public |
|---|---:|---:|---:|---:|
| Core Backend | Mounted | No | No | Mounted |
| Incident Service | No | Mounted | Mounted | No |
| Frontend | No | No | No | No |
| PostgreSQL | No | No | No | No |

The private key:

- is generated locally;
- is stored below `.opsflow-secrets/`;
- is excluded from Git;
- is mounted only into its owning service container;
- is never copied into an image;
- is never stored in an environment variable;
- is never printed by the application.

The public key is not confidential, but it is still managed
as a file-backed Compose secret so distribution remains
explicit and auditable.

## Generate the local key pairs

Run from the repository root in Git Bash:

```bash
./backend/.venv/Scripts/python.exe \
  scripts/generate_service_identity_keys.py

./incident-service/.venv/Scripts/python.exe \
  scripts/generate_incident_service_identity_keys.py
```

The command creates:

```text
.opsflow-secrets/
├── core-service-identity-private.pem
├── core-service-identity-public.pem
├── incident-service-identity-private.pem
└── incident-service-identity-public.pem
```

The generator refuses to overwrite either file. Never
replace a private key while retaining the same key ID.

## Verify local files without printing key material

```bash
test -f ./.opsflow-secrets/core-service-identity-private.pem \
  && echo "PASS: private key exists" \
  || echo "FAIL: private key is missing"

test -f ./.opsflow-secrets/core-service-identity-public.pem \
  && echo "PASS: public key exists" \
  || echo "FAIL: public key is missing"

test -f ./.opsflow-secrets/incident-service-identity-private.pem \
  && echo "PASS: Incident private key exists" \
  || echo "FAIL: Incident private key is missing"

test -f ./.opsflow-secrets/incident-service-identity-public.pem \
  && echo "PASS: Incident public key exists" \
  || echo "FAIL: Incident public key is missing"
```

Confirm that the public key matches the private key:

```bash
openssl pkey \
  -in ./.opsflow-secrets/core-service-identity-private.pem \
  -pubout \
  -outform DER \
  | sha256sum

openssl pkey \
  -pubin \
  -in ./.opsflow-secrets/core-service-identity-public.pem \
  -outform DER \
  | sha256sum
```

The two fingerprints must match.

Repeat the match check for the Incident Service pair:

```bash
openssl pkey \
  -in ./.opsflow-secrets/incident-service-identity-private.pem \
  -pubout \
  -outform DER \
  | sha256sum

openssl pkey \
  -pubin \
  -in ./.opsflow-secrets/incident-service-identity-public.pem \
  -outform DER \
  | sha256sum
```

Those two fingerprints must also match.

## Verify Git exclusion

```bash
git check-ignore -v \
  .opsflow-secrets/core-service-identity-private.pem \
  .opsflow-secrets/core-service-identity-public.pem \
  .opsflow-secrets/incident-service-identity-private.pem \
  .opsflow-secrets/incident-service-identity-public.pem
```

Both paths must be reported as ignored. Never use
`git add -f` on either key.

## Validate resolved Compose configuration

Always supply the project Compose environment file:

```bash
docker compose --env-file .env.docker config --quiet
```

The resolved secret sources can be inspected without
printing key contents:

```bash
docker compose --env-file .env.docker config \
  | grep -n -A 3 -B 1 \
      "service_identity"
```

The Backend receives the private key at:

```text
/run/secrets/core_service_identity_private_key
```

The Incident Service receives the public key at:

```text
/run/secrets/core_service_identity_public_key
```

The Incident Service receives its private key at:

```text
/run/secrets/incident_service_identity_private_key
```

The Backend receives the Incident public key at:

```text
/run/secrets/incident_service_identity_public_key
```

## Start the distributed stack

```bash
docker compose --env-file .env.docker up -d --build

docker compose --env-file .env.docker ps
```

Wait until both `backend` and `incident-service` report
healthy before continuing.

## Verify runtime key isolation

Verify the Backend receives only its private key and the
Incident public key:

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "from pathlib import Path; core_private = Path('/run/secrets/core_service_identity_private_key'); core_public = Path('/run/secrets/core_service_identity_public_key'); incident_private = Path('/run/secrets/incident_service_identity_private_key'); incident_public = Path('/run/secrets/incident_service_identity_public_key'); assert core_private.is_file(); assert not core_public.exists(); assert not incident_private.exists(); assert incident_public.is_file(); print('PASS: Backend key isolation verified')"
```

Verify the Incident Service receives the Core public key and
only its own private key:

```bash
docker compose --env-file .env.docker exec -T incident-service \
  python -c "from pathlib import Path; core_private = Path('/run/secrets/core_service_identity_private_key'); core_public = Path('/run/secrets/core_service_identity_public_key'); incident_private = Path('/run/secrets/incident_service_identity_private_key'); incident_public = Path('/run/secrets/incident_service_identity_public_key'); assert not core_private.exists(); assert core_public.is_file(); assert incident_private.is_file(); assert not incident_public.exists(); print('PASS: Incident Service key isolation verified')"
```

## Verify a real signed request

The following command creates a short-lived read credential
inside the Backend container and calls the private Incident
Service. It never prints the token.

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "import httpx; from app.core.config import settings; from app.core.service_identity import ServiceScope; from app.core.service_identity_provider import get_service_token_provider; token = get_service_token_provider().create_token(audience=settings.incident_service_audience, scopes={ServiceScope.INCIDENTS_READ}); response = httpx.get('http://incident-service:8000/api/v1/incidents', headers={'Authorization': f'Bearer {token}'}, timeout=5.0); assert response.status_code == 200, (response.status_code, response.text); print('PASS: signed Incident Service read accepted')"
```

## Verify rejection contracts

Missing credentials must produce `401` and advertise the
Bearer challenge:

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "import httpx; response = httpx.get('http://incident-service:8000/api/v1/incidents', timeout=5.0); assert response.status_code == 401, (response.status_code, response.text); assert response.headers.get('WWW-Authenticate') == 'Bearer'; print('PASS: missing credential rejected')"
```

A valid write-only credential must not authorize a read:

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "import httpx; from app.core.config import settings; from app.core.service_identity import ServiceScope; from app.core.service_identity_provider import get_service_token_provider; token = get_service_token_provider().create_token(audience=settings.incident_service_audience, scopes={ServiceScope.INCIDENTS_WRITE}); response = httpx.get('http://incident-service:8000/api/v1/incidents', headers={'Authorization': f'Bearer {token}'}, timeout=5.0); assert response.status_code == 403, (response.status_code, response.text); print('PASS: insufficient scope rejected')"
```

## Current migration boundary

Core-to-Incident bearer authentication is active. The reverse
Incident-to-Core path retains the shared header until the
Phase 10.6 route cutover. Phase 10.6D distributes the reverse
keypair but does not change live authentication by itself.

## Rotation preparation

The current local-development key ID is:

```text
core-backend-key-1
incident-service-key-1
```

Rotation requires:

1. Generate a new RSA key pair.
2. Assign a new key ID.
3. Distribute the new public key to verifiers.
4. Retain the previous public key during a bounded overlap.
5. Switch the issuer to the new private key and key ID.
6. Wait longer than the maximum service-token lifetime.
7. Remove the previous public key.

Never replace a private key under an existing key ID.
