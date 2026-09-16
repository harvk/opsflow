Service Identity Key Provisioning
This runbook provisions the local-development RSA keypair
used by the OpsFlow Core Backend to issue short-lived service
JWTs.
It does not provision production credentials. Production
deployments should use the secret-management facility of the
selected deployment platform.
Security boundary
The Core Backend owns the private signing key.
The private key:
is generated locally;
is stored below `.opsflow-secrets/`;
is excluded from Git;
is mounted only into the Backend container;
is never copied into a Docker image;
is never stored in an environment variable;
is never printed by the application.
The public key is not secret. It will be distributed to the
Incident Service when inbound service-JWT verification is
implemented.
Generate the local keypair
Run from the repository root in Git Bash:

```bash
./backend/.venv/Scripts/python.exe \
  scripts/generate_service_identity_keys.py
```

The command creates:

```text
.opsflow-secrets/
├── core-service-identity-private.pem
└── core-service-identity-public.pem
```

The generator refuses to overwrite either file. Key rotation
must use a deliberate new key identifier and controlled
replacement procedure.
Verify Git exclusion
Run:

```bash
git check-ignore -v \
  .opsflow-secrets/core-service-identity-private.pem \
  .opsflow-secrets/core-service-identity-public.pem
```

Both paths must be reported as ignored by `.gitignore`.
Confirm that neither key appears in repository status:

```bash
git status --short
```

Never use `git add -f` on either key.
Validate Docker Compose
Run:

```bash
docker compose --env-file .env.docker config --quiet
```

The Backend receives the private key at:

```text
/run/secrets/core_service_identity_private_key
```

The Incident Service must not receive that file.
Verify runtime isolation
After starting the stack, verify that Core can issue a token
without printing the credential:

```bash
docker compose --env-file .env.docker exec -T backend \
  python -c "from app.core.config import settings; from app.core.service_identity import ServiceScope; from app.core.service_identity_provider import get_service_token_provider; token = get_service_token_provider().create_token(audience=settings.incident_service_audience, scopes={ServiceScope.INCIDENTS_READ}); assert token.count('.') == 2; print('Core service identity issuance passed')"
```

Verify that the Incident Service cannot see Core's private
key:

```bash
docker compose --env-file .env.docker exec -T incident-service \
  /bin/sh -c 'test ! -e /run/secrets/core_service_identity_private_key'
```

The isolation command succeeds silently.
Rotation preparation
The current local-development key identifier is:

```text
core-backend-key-1
```

Rotation requires:
generating a new RSA keypair;
assigning a new `kid`;
distributing the new public key to verifiers;
allowing the previous public key during a bounded overlap;
switching the issuer to the new private key;
removing the previous public key after all older tokens
have expired.
Do not replace the current private key under the same `kid`.
