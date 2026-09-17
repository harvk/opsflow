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

## Verify Incident-to-Core authentication

The reverse path uses an independently signed Incident
Service credential. The command below uses a nonexistent
service ID so verification does not modify application data.

```bash
docker compose --env-file .env.docker exec -T incident-service \
  python -c "import httpx; from app.core.config import get_settings; from app.core.service_identity import ServiceScope; from app.core.service_token_provider import get_service_token_provider; settings = get_settings(); token = get_service_token_provider().create_token(audience=settings.core_backend_audience, scopes={ServiceScope.SERVICES_READ}); response = httpx.get(f'{settings.core_backend_url}/internal/services/00000000-0000-4000-8000-000000000001/exists', headers={'Authorization': f'Bearer {token}'}, timeout=5.0); assert response.status_code == 200, (response.status_code, response.text); assert response.json() == {'exists': False}; print('PASS: Incident-signed services:read token accepted')"
```

Verify that the retired shared header is rejected:

```bash
docker compose --env-file .env.docker exec -T incident-service \
  python -c "import httpx; from app.core.config import get_settings; settings = get_settings(); response = httpx.get(f'{settings.core_backend_url}/internal/services/00000000-0000-4000-8000-000000000001/exists', headers={'X-OpsFlow-Internal-Token': 'retired-shared-secret'}, timeout=5.0); assert response.status_code == 401; assert response.json() == {'detail': 'Invalid service credentials.'}; assert 'retired-shared-secret' not in response.text; print('PASS: retired shared header rejected')"
```

## Verify security observability

Both services expose bounded authentication and authorization
counters:

```text
opsflow_service_authentication_attempts_total
opsflow_service_authorization_decisions_total
```

Inspect only those metrics in the Backend:

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "import urllib.request; text = urllib.request.urlopen('http://127.0.0.1:8000/metrics', timeout=5).read().decode(); print('\\n'.join(line for line in text.splitlines() if line.startswith('opsflow_service_authentication_attempts_total') or line.startswith('opsflow_service_authorization_decisions_total')))"
```

Use the same command with `incident-service` in place of
`backend` to inspect the receiving Incident Service process.

Inspect structured service-security events:

```bash
docker compose --env-file .env.docker logs \
  --no-color \
  --since 15m \
  backend \
  incident-service \
  | grep -E \
    '"event":"service_(authentication|authorization)"'
```

Events may contain only generated event metadata, a validated
request ID, a bounded outcome, a bounded reason, and a
registered scope. They must not contain credentials, JWT
claims, keys, raw headers, or exception messages.

## Current migration boundary

Bidirectional RS256 service authentication is active:

```text
Core Backend     -> Incident Service
Incident Service -> Core Backend
```

Each service owns a distinct private key and receives only the
other service's public key. The static shared token and
`X-OpsFlow-Internal-Token` authentication path are retired and
must remain rejected.

Service JWTs are stateless and may be reused during their
short lifetime. OpsFlow does not currently maintain a
distributed `jti` replay cache.

## Rotation preparation

The current local-development key ID is:

```text
core-backend-key-1
incident-service-key-1
```

### Core signing-key rotation

Incident Service supports a bounded overlap between the
current and previous Core public keys. Core signing-key
rotation uses this sequence:

1. Generate a new RSA key pair.
2. Assign a new key ID.
3. Distribute the new public key to verifiers.
4. Retain the previous public key during a bounded overlap.
5. Switch the issuer to the new private key and key ID.
6. Wait longer than the maximum service-token lifetime.
7. Remove the previous public key.

Never replace a private key under an existing key ID.

### Incident signing-key rotation

Core Backend currently loads one Incident Service public key.
Incident signing-key rotation therefore requires a coordinated
deployment:

1. Generate a replacement Incident RSA key pair.
2. Assign a new Incident key ID.
3. Update Core's Incident verification key and key ID.
4. Update Incident Service's signing key and key ID within the
   coordinated deployment window.
5. Verify Incident-to-Core authentication immediately after
   deployment.

The current Incident-to-Core path must not be described as
supporting current/previous-key overlap or zero-downtime key
rotation.
