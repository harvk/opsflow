# OpsFlow — Production container configuration

This package was created from `opsflow_upload_deploy.zip`, not inferred from
an earlier generic example. It prepares production configuration **offline**.
It does not contact AWS, update Terraform, deploy to EC2, read credentials,
or modify RDS. That work belongs to 12.6D after validation.

## Files supplied

- `backend/app/core/config.py` — complete source file; change only the
  `TEST_DATABASE_URL` setting to default to the empty string for production.
  Local and CI tests continue to supply their existing test database URL.
- `frontend/Dockerfile` — complete existing Dockerfile with one additional
  `NGINX_SITE_CONF` build argument. Without this argument it still uses
  the existing `frontend/nginx/default.conf` for local development.
- `frontend/nginx/production.conf` — production static server and **same-origin**
  `/api/` reverse proxy; URI paths are preserved.
- `compose.production.yaml` — **independent** Compose configuration; never
  merge with local `compose.yaml` or `compose.aws-local.yaml`.
- `.env.production.example` — non-secret deployment variable inventory; it
  contains conspicuous placeholders and is **not deployable as supplied**.
- `scripts/deployment/phase12_6/source_sha256.json` — uploaded-file checksums
  for the two modified existing application files.
- `scripts/deployment/phase12_6/install_phase12_6c.py` — refuses to overwrite
  existing application files whose bytes differ from the audited upload.
- `scripts/deployment/phase12_6/verify_production_config.py` — offline checks.
- `scripts/deployment/phase12_6/test_production_config.py` — six unit tests.

## On Windows Git Bash: install without losing changes

1. Save `opsflow_phase12_6c_package.zip` in the repository root, **not inside
   `infrastructure/terraform`**. Work on `feature/live-deploy` with a clean
   working tree and preserve source database backups.
2. At repository root, run:

   ```bash
   mkdir -p .opsflow-migration/phase12-6c-package
   unzip -t opsflow_phase12_6c_package.zip
   unzip -n opsflow_phase12_6c_package.zip -d .opsflow-migration/phase12-6c-package
   backend/.venv/Scripts/python.exe \
     .opsflow-migration/phase12-6c-package/scripts/deployment/phase12_6/install_phase12_6c.py
   ```

   Do not run any Python **source** directly in Git Bash. The installer is
   invoked using your Python executable. If it reports `SAFETY STOP`, stop;
   do not force an overwrite of changed application code.

3. Safely ignore future local credentials and release-runtime files:

   ```bash
   touch .gitignore
   grep -Fxq '/.env.production' .gitignore || printf '%s\n' '/.env.production' >> .gitignore
   grep -Fxq '/.opsflow-runtime/' .gitignore || printf '%s\n' '/.opsflow-runtime/' >> .gitignore
   grep -Fxq '/.opsflow-migration/' .gitignore || printf '%s\n' '/.opsflow-migration/' >> .gitignore
   ```

4. Validate using the local backend Python interpreter:

   ```bash
   backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/verify_production_config.py
   backend/.venv/Scripts/python.exe -m unittest discover \
     -s scripts/deployment/phase12_6 -p 'test_production_config.py' -v
   backend/.venv/Scripts/python.exe -m py_compile backend/app/core/config.py
   git diff --check
   git status --short
   ```

5. Optionally verify the production frontend image **locally**, without any
   AWS resources or application secrets. In Windows Git Bash:

   ```bash
   docker build --platform linux/amd64 \
     --build-arg NODE_VERSION=24 \
     --build-arg VITE_API_BASE_URL=/api/v1 \
     --build-arg NGINX_SITE_CONF=nginx/production.conf \
     -t opsflow-frontend:phase12-6c-validation ./frontend
   ```

   The final production image must not have `localhost:8000` baked into its
   browser assets. `VITE_API_BASE_URL=/api/v1` ensures same-origin routing.
   This command tests the frontend build only; do not start the live stack.

6. Review changes, then stage only this phase's source files and ignore rules:

   ```bash
   git add .gitignore compose.production.yaml .env.production.example \
     backend/app/core/config.py frontend/Dockerfile frontend/nginx/production.conf \
     scripts/deployment/phase12_6/install_phase12_6c.py \
     scripts/deployment/phase12_6/source_sha256.json \
     scripts/deployment/phase12_6/verify_production_config.py \
     scripts/deployment/phase12_6/test_production_config.py \
     PHASE_12_6C_README.md
   git diff --cached --check
   git diff --cached --stat
   git commit -m 'feat(deploy): prepare isolated production Compose and same-origin routing'
   git push -u origin feature/live-deploy
   ```

   If the installer has not been run or the tests fail, do not commit.

## Production design notes and stop conditions

- Core and Incident are on isolated Compose service networks, with Core also
  on the frontend edge network so NGINX can proxy the API.
- Core and Incident are **not** published to the EC2 host. NGINX is initially
  bound only to `127.0.0.1:8080`. Phase 12.7 will require an explicit mapping
  update and ALB-only EC2 security-group ingress before public traffic.
- Both databases remain on RDS. There is **no** local PostgreSQL or automatic
  Alembic upgrade service. In 12.6D, compare current migration heads to the
  restored databases **before** deciding whether to apply schema changes.
- The production backend does not require `TEST_DATABASE_URL`, but tests still
  provide that value in their own test environments.
- `.opsflow-runtime/backend.env` and `incident.env` will be created **on EC2**
  by a separate trusted deployment step using the two existing restricted DB
  Secrets Manager secrets. Never commit these files, paste passwords into a
  shell, or use your RDS master credential as an application password.
- `.opsflow-runtime/secrets` will hold the two existing service-identity key
  pairs, with private keys readable only by the appropriate container UID.
  These keys are not distributed in this package.
- Workers use the `workers` profile and MUST NOT be enabled until we have
  verified the scoped AWS instance-role permissions for SES, SQS and
  DynamoDB and measured actual memory consumption. A `t3.small` has limited RAM.
  The single-host EC2 instance role is shared: IAM is not a container-specific
  security boundary.
- The backend's production cookie settings require HTTPS. **Do not test login
  using a public plain-HTTP IP address.** First use SSM loopback health checks,
  then route browsers through the HTTPS ALB/domain.
- Do **not** use `compose.aws-local.yaml` in production; it mounts developer
  AWS credentials and disables instance metadata credentials.
- `docker compose --env-file .env.production -f compose.production.yaml config`
  is a 12.6D check after actual non-secret interpolation values and trusted
  runtime environment files have been prepared. The example file still
  contains placeholders; running it now is not a deployment readiness test.

## Next: 12.6D

Prepare the release archive and secure EC2 transfer, generate production
application secrets (separate from DB secrets), set up verified service-identity
key transfer, pull the existing RDS DB-login secrets, configure narrowly scoped
AWS service IAM access, compare Alembic revisions, and run the core three
containers through SSM. Keep workers off until permissions and capacity pass.
No public listener or inbound security group rule will be introduced until ALB.
