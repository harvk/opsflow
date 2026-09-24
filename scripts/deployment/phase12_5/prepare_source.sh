#!/usr/bin/env bash
set -Eeuo pipefail

# Run from repository root in Windows Git Bash.
# Explicit guard: human must stop ALL application/worker writers first.
if [[ "${CONFIRM_WRITERS_STOPPED:-}" != "YES" ]]; then
  echo "STOP: Quiesce all local writers and set CONFIRM_WRITERS_STOPPED=YES." >&2
  exit 1
fi
[[ -f .env.docker ]] || { echo 'Run from repository root.' >&2; exit 1; }

script_dir="scripts/deployment/phase12_5"
artifacts=".opsflow-migration/rds/final"
mkdir -p "$artifacts"

# Fresh snapshots ONLY. Fail instead of overwriting earlier final snapshots.
for f in opsflow.dump opsflow_incidents.dump SHA256SUMS; do
  [[ ! -e "$artifacts/$f" ]] || {
    echo "STOP: Existing $artifacts/$f; inspect it before re-running." >&2
    exit 1
  }
done

for db in opsflow opsflow_incidents; do
  echo "Recording source row counts: $db"
  docker compose --env-file .env.docker exec -T db \
    sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -A -t -F "|" -P pager=off' \
    sh "$db" \
    < "$script_dir/table_counts.sql" \
    > "$artifacts/${db}.table_counts.txt"

  echo "Recording local Alembic revision: $db"
  found="$(docker compose --env-file .env.docker exec -T db \
    sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -A -t -c "SELECT to_regclass('\''public.alembic_version'\'') IS NOT NULL;"' \
    sh "$db" | tr -d '\r')"
  if [[ "$found" == t ]]; then
    docker compose --env-file .env.docker exec -T db \
      sh -c 'exec psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -A -t -c "SELECT version_num FROM public.alembic_version ORDER BY version_num;"' \
      sh "$db" | tr -d '\r' > "$artifacts/${db}.alembic.txt"
  else
    printf '%s\n' '<no public.alembic_version table>' > "$artifacts/${db}.alembic.txt"
  fi

  echo "Creating PostgreSQL 18 custom-format archive: $db"
  docker compose --env-file .env.docker exec -T db \
    sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$1" -Fc' \
    sh "$db" \
    > "$artifacts/${db}.dump"
  test -s "$artifacts/${db}.dump"

  # Catalog check is a useful preflight, but a successful restore is the
  # definitive integrity test. No host/container path translation involved.
  docker compose --env-file .env.docker exec -T db pg_restore --list \
    < "$artifacts/${db}.dump" \
    > "$artifacts/${db}.catalog.txt"
  test -s "$artifacts/${db}.catalog.txt"
done

(
  cd "$artifacts"
  sha256sum opsflow.dump opsflow_incidents.dump > SHA256SUMS
  sha256sum -c SHA256SUMS
)

echo 'PASS: Fresh archives, catalogs, exact per-table counts and checksums captured.'
echo 'KEEP ALL WRITERS STOPPED until RDS cutover or consciously repeat this phase.'
