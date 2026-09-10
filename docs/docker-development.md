# OpsFlow Docker Development

This document describes the local Docker development workflow for OpsFlow.

## Architecture

The local stack contains four Docker Compose services:

- `db` — PostgreSQL
- `migrate` — one-shot Alembic migration runner
- `backend` — FastAPI application
- `frontend` — React + TypeScript + Vite development server

The expected steady-state service status is:

```text
db          Up / healthy
migrate     Exited (0)
backend     Up
frontend    Up
```

`migrate` is intentionally a one-shot service. `Exited (0)` means the
migration process completed successfully.

## Local URLs

Frontend:

```text
http://localhost:5173
```

Backend OpenAPI documentation:

```text
http://localhost:8000/docs
```

Backend OpenAPI schema:

```text
http://localhost:8000/openapi.json
```

The browser-side frontend API base URL is:

```text
http://localhost:8000/api/v1
```

Do not configure browser-side React code to use:

```text
http://backend:8000
```

`backend` is a Docker-internal DNS name. Browser JavaScript runs on the
host and therefore reaches FastAPI through the published localhost port.

## Environment Files

Local runtime environment files are not committed:

```text
.env.docker
frontend/.env.docker
```

Documented templates are committed:

```text
.env.docker.example
frontend/.env.docker.example
```

Do not place secrets in `VITE_*` variables. Vite variables can become
visible to browser-side JavaScript.

## Start the Stack

From the repository root:

```bash
docker compose \
  --env-file .env.docker \
  up -d
```

Check status:

```bash
docker compose \
  --env-file .env.docker \
  ps -a
```

## Build and Start

When Dockerfiles, backend dependencies, frontend dependencies, or other
image inputs have changed:

```bash
docker compose \
  --env-file .env.docker \
  up -d --build
```

## Stop the Stack

Normal shutdown:

```bash
docker compose \
  --env-file .env.docker \
  down
```

Do not routinely use:

```bash
docker compose \
  --env-file .env.docker \
  down -v
```

The `-v` option removes named volumes and can delete local PostgreSQL
data.

## Frontend Development

The host frontend directory is bind-mounted into:

```text
/app
```

inside the frontend container.

The frontend dependency directory:

```text
/app/node_modules
```

is backed by the Docker-managed named volume:

```text
opsflow_frontend_node_modules
```

This prevents Windows-installed Node dependencies from replacing Linux
container dependencies.

Normal React/TypeScript/CSS source changes do not require an image
rebuild.

Vite HMR detects source changes and updates the browser automatically.

## Frontend Dependencies

Install a frontend dependency through the running frontend container:

```bash
docker compose \
  --env-file .env.docker \
  exec frontend \
  npm install <package>
```

After changing `package.json` or `package-lock.json`, verify that the
image remains reproducible:

```bash
docker compose \
  --env-file .env.docker \
  build frontend
```

## Backend Dependencies

Backend dependencies must be recorded in the backend dependency
manifest and incorporated through an image rebuild.

Do not rely on an ad-hoc `pip install` inside the running backend
container because that change disappears when the container is
recreated.

Rebuild the backend with:

```bash
docker compose \
  --env-file .env.docker \
  up -d --build backend
```

## Frontend Tests

Run:

```bash
docker compose \
  --env-file .env.docker \
  exec frontend \
  npx vitest run
```

## Backend Tests

The runtime backend image intentionally does not contain the complete
repository test tree.

The backend suite also contains cross-stack tests that inspect frontend
source files.

From Git Bash on Windows, run:

```bash
MSYS_NO_PATHCONV=1 docker compose \
  --env-file .env.docker \
  run \
  --rm \
  --no-deps \
  --workdir /app \
  --volume "$(pwd -W):/workspace:ro" \
  -e PYTHONPATH=/app \
  -e PYTHONDONTWRITEBYTECODE=1 \
  backend \
  python -m pytest \
  -p no:cacheprovider \
  /workspace/backend/tests
```

The repository is mounted read-only at `/workspace`, while the
Dockerized backend application remains available at `/app`.

## Run Migrations

Run the one-shot migration service:

```bash
docker compose \
  --env-file .env.docker \
  run --rm migrate
```

A successful migration process exits with status code `0`.

Check the persistent Compose migration container with:

```bash
docker compose \
  --env-file .env.docker \
  ps -a migrate
```

If needed, inspect its exit code:

```bash
docker inspect \
  "$(docker compose --env-file .env.docker ps -a -q migrate)" \
  --format 'ExitCode={{.State.ExitCode}}'
```

## Logs

Backend:

```bash
docker compose \
  --env-file .env.docker \
  logs --tail=100 backend
```

Frontend:

```bash
docker compose \
  --env-file .env.docker \
  logs --tail=100 frontend
```

Database:

```bash
docker compose \
  --env-file .env.docker \
  logs --tail=100 db
```

Follow logs:

```bash
docker compose \
  --env-file .env.docker \
  logs -f backend
```

Pressing `Ctrl+C` while following logs stops only the log viewer. It
does not stop the container.

## Container Shells

Backend:

```bash
docker compose \
  --env-file .env.docker \
  exec backend \
  sh
```

Frontend:

```bash
docker compose \
  --env-file .env.docker \
  exec frontend \
  sh
```

## Git Bash Path Conversion

Git Bash on Windows can rewrite Linux container paths such as:

```text
/app
```

into Windows paths.

For Docker commands that pass absolute Linux paths, disable MSYS path
conversion for that command:

```bash
MSYS_NO_PATHCONV=1 docker ...
```

## Docker Exec and Heredocs

When feeding a script to `docker compose exec` through standard input,
disable TTY allocation with `-T`.

Example:

```bash
docker compose \
  --env-file .env.docker \
  exec -T backend \
  python - <<'PY'
print("Hello from OpsFlow")
PY
```

## Service Recovery

Restart a running service:

```bash
docker compose \
  --env-file .env.docker \
  restart backend
```

Start a stopped service:

```bash
docker compose \
  --env-file .env.docker \
  start backend
```

Recreate a service without rebuilding its image:

```bash
docker compose \
  --env-file .env.docker \
  up -d \
  --force-recreate \
  --no-deps \
  backend
```

Rebuild and recreate a service:

```bash
docker compose \
  --env-file .env.docker \
  up -d --build backend
```

## Persistent Volumes

Important local volumes include:

```text
opsflow_postgres_data
opsflow_frontend_node_modules
```

The PostgreSQL volume contains local development data.

Do not remove it as a generic troubleshooting step.

Inspect volumes with:

```bash
docker volume ls | grep opsflow
```

## Troubleshooting Order

When a service fails:

1. Inspect Compose state.

   ```bash
   docker compose --env-file .env.docker ps -a
   ```

2. Inspect the affected service logs.

3. Inspect its exit code when appropriate.

4. Determine whether the problem requires a restart, recreation, or
   image rebuild.

5. Avoid destructive volume removal unless data destruction is
   explicitly intended.

The preferred strategy is always to perform the smallest Docker
operation required to correct the problem.
