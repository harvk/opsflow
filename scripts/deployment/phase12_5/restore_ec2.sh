#!/usr/bin/env bash
set -Eeuo pipefail
set +x # Never log the RDS master secret.
umask 077

# Run as root via sudo env on the EC2 host, NOT on Windows.
# Requirements are intentionally supplied as non-secret environment variables.
for name in AWS_REGION MIGRATION_BUCKET RDS_HOST RDS_SECRET_ARN; do
  [[ -n "${!name:-}" ]] || { echo "Missing environment value: $name" >&2; exit 1; }
done
[[ "$(id -u)" == 0 ]] || { echo 'Run this script with sudo.' >&2; exit 1; }
[[ "$RDS_HOST" =~ ^[a-zA-Z0-9.-]+$ ]] || { echo 'Invalid RDS hostname.' >&2; exit 1; }
[[ "$MIGRATION_BUCKET" =~ ^[a-z0-9.-]+$ ]] || { echo 'Invalid bucket name.' >&2; exit 1; }

workdir="/opt/opsflow/.rds-migration"
mkdir -p "$workdir"
chmod 0700 "$workdir"

cleanup_secret() {
  rm -f "$workdir/.pgpass"
  unset master_json password PG_USER || true
}
trap cleanup_secret EXIT

command -v aws >/dev/null || { echo 'AWS CLI missing on EC2.' >&2; exit 1; }
command -v docker >/dev/null || { echo 'Docker missing on EC2.' >&2; exit 1; }
command -v jq >/dev/null || { echo 'jq missing on EC2.' >&2; exit 1; }
command -v curl >/dev/null || { echo 'curl missing on EC2.' >&2; exit 1; }

# Fail closed if any archive is already present from a partially completed run.
for f in opsflow.dump opsflow_incidents.dump; do
  [[ ! -e "$workdir/$f" ]] || {
    echo "STOP: Existing $workdir/$f. Inspect previous migration attempt; do not rerun blindly." >&2
    exit 1
  }
done

for f in \
  opsflow.dump opsflow_incidents.dump SHA256SUMS \
  opsflow.table_counts.txt opsflow_incidents.table_counts.txt \
  opsflow.alembic.txt opsflow_incidents.alembic.txt \
  table_counts.sql
do
  aws s3 cp \
    "s3://${MIGRATION_BUCKET}/phase12-5/${f}" \
    "$workdir/$f" \
    --region "$AWS_REGION" --only-show-errors
  chmod 0600 "$workdir/$f"
done

(
  cd "$workdir"
  sha256sum -c SHA256SUMS
)

curl -fsSL --retry 3 \
  'https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem' \
  -o "$workdir/global-bundle.pem"
grep -q -- 'BEGIN CERTIFICATE' "$workdir/global-bundle.pem"
chmod 0600 "$workdir/global-bundle.pem"

echo 'Retrieving the RDS-managed credential directly on EC2 (not printing it).'
master_json="$(aws secretsmanager get-secret-value \
  --secret-id "$RDS_SECRET_ARN" \
  --region "$AWS_REGION" \
  --query 'SecretString' --output text)"
PG_USER="$(printf '%s' "$master_json" | jq -er '.username')"
password="$(printf '%s' "$master_json" | jq -er '.password')"
[[ "$PG_USER" == 'opsflow_admin' ]] || {
  echo 'Unexpected RDS master username. Review RDS configuration before continuing.' >&2
  exit 1
}
[[ -n "$password" ]] || { echo 'Empty secret password.' >&2; exit 1; }

pgpass_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//:/\\:}"
  printf '%s' "$value"
}
printf '%s:%s:*:%s:%s\n' \
  "$(pgpass_escape "$RDS_HOST")" \
  '5432' \
  "$(pgpass_escape "$PG_USER")" \
  "$(pgpass_escape "$password")" \
  > "$workdir/.pgpass"
chmod 0600 "$workdir/.pgpass"
unset master_json password

# Use the SAME PostgreSQL 18.6 major/minor client for restore.
# Running inside EC2 means normal Linux Docker paths; no MSYS path rewriting.
echo 'Pulling official PostgreSQL 18.6 client image.'
docker pull postgres:18.6-bookworm >/dev/null

pgclient() {
  docker run --rm --network host \
    -v "$workdir:/work:ro" \
    -e "PGHOST=$RDS_HOST" \
    -e PGPORT=5432 \
    -e "PGUSER=$PG_USER" \
    -e PGSSLMODE=verify-full \
    -e PGSSLROOTCERT=/work/global-bundle.pem \
    -e PGPASSFILE=/work/.pgpass \
    postgres:18.6-bookworm "$@"
}

echo 'Checking verified-TLS database connectivity and PostgreSQL engine version.'
pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
  -c 'SELECT current_setting('\''server_version'\'');'
pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
  -c 'SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid();' \
  | grep -qx t

echo 'Checking initial target database state (must be empty).'
main_exists="$(pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
  -c "SELECT 1 FROM pg_database WHERE datname='opsflow';" | tr -d '\r')"
[[ "$main_exists" == 1 ]] || { echo 'Expected Terraform-created opsflow DB missing.' >&2; exit 1; }

for db in opsflow opsflow_incidents; do
  exists="$(pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
    -c "SELECT 1 FROM pg_database WHERE datname='$db';" | tr -d '\r')"
  if [[ "$exists" == 1 ]]; then
    table_count="$(pgclient psql -X -v ON_ERROR_STOP=1 -d "$db" -A -t \
      -c "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema');" | tr -d '\r')"
    [[ "$table_count" == 0 ]] || {
      echo "STOP: Target $db already has $table_count application tables; refusing to overwrite." >&2
      exit 1
    }
  fi
done

# The second database does not exist in Terraform's initial db_name definition.
incident_exists="$(pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
  -c "SELECT 1 FROM pg_database WHERE datname='opsflow_incidents';" | tr -d '\r')"
if [[ "$incident_exists" != 1 ]]; then
  pgclient createdb --maintenance-db=postgres opsflow_incidents
fi

for db in opsflow opsflow_incidents; do
  echo "Restoring $db (the archive will not overwrite non-empty databases)."
  pgclient pg_restore \
    --exit-on-error --no-owner --no-acl \
    --dbname "$db" \
    "/work/${db}.dump" \
    > "$workdir/${db}.restore.log" 2>&1 || {
      echo "RESTORE FAILED for $db. Review $workdir/${db}.restore.log ON EC2." >&2
      echo 'Database may now be partially populated. Do not rerun automatically.' >&2
      exit 1
    }

  # Generate exact table counts and compare to locally audited source.
  pgclient psql -X -v ON_ERROR_STOP=1 -d "$db" -A -t -F '|' -P pager=off \
    -f /work/table_counts.sql \
    > "$workdir/${db}.restored_table_counts.txt"
  diff -u \
    "$workdir/${db}.table_counts.txt" \
    "$workdir/${db}.restored_table_counts.txt" || {
      echo "STOP: Per-table row counts do not match for $db." >&2
      exit 1
    }

  version_table="$(pgclient psql -X -v ON_ERROR_STOP=1 -d "$db" -A -t \
    -c "SELECT to_regclass('public.alembic_version') IS NOT NULL;" | tr -d '\r')"
  if [[ "$version_table" == t ]]; then
    pgclient psql -X -v ON_ERROR_STOP=1 -d "$db" -A -t \
      -c 'SELECT version_num FROM public.alembic_version ORDER BY version_num;' \
      > "$workdir/${db}.restored_alembic.txt"
  else
    printf '%s\n' '<no public.alembic_version table>' \
      > "$workdir/${db}.restored_alembic.txt"
  fi
  diff -u \
    "$workdir/${db}.alembic.txt" \
    "$workdir/${db}.restored_alembic.txt" || {
      echo "STOP: Alembic revision differs for $db." >&2
      exit 1
    }
  echo "PASS: $db exact table counts and Alembic revisions match."
done

# Prepare independent least-privileged app roles (NOLOGIN until Phase 12.6).
# Restored schema objects remain owned by opsflow_admin, the migration owner.
# Future migrations should run with a separate tightly controlled migration
# credential, not with the runtime role.
for role in opsflow_app opsflow_incidents_app; do
  exists="$(pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t \
    -c "SELECT 1 FROM pg_roles WHERE rolname='$role';" | tr -d '\r')"
  if [[ "$exists" != 1 ]]; then
    pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -c "CREATE ROLE $role NOLOGIN;"
  fi
done

pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -c \
  'GRANT CONNECT ON DATABASE opsflow TO opsflow_app; GRANT CONNECT ON DATABASE opsflow_incidents TO opsflow_incidents_app;'

for spec in 'opsflow:opsflow_app' 'opsflow_incidents:opsflow_incidents_app'; do
  db="${spec%%:*}"
  role="${spec#*:}"
  pgclient psql -X -v ON_ERROR_STOP=1 -d "$db" -c \
    "GRANT USAGE ON SCHEMA public TO $role;
     GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO $role;
     GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO $role;
     ALTER DEFAULT PRIVILEGES FOR ROLE opsflow_admin IN SCHEMA public
       GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO $role;
     ALTER DEFAULT PRIVILEGES FOR ROLE opsflow_admin IN SCHEMA public
       GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO $role;"
done

# Verify no runtime login has been enabled accidentally, even when roles
# already existed before this script was run.
role_state="$(pgclient psql -X -v ON_ERROR_STOP=1 -d postgres -A -t -F '|' \
  -c "SELECT rolname, rolcanlogin FROM pg_roles
      WHERE rolname IN ('opsflow_app','opsflow_incidents_app') ORDER BY rolname;")"
expected_role_state="$(printf '%s\n%s' 'opsflow_app|f' 'opsflow_incidents_app|f')"
[[ "$role_state" == "$expected_role_state" ]] || {
  echo 'STOP: Unexpected application role configuration; both must be NOLOGIN.' >&2
  exit 1
}
echo 'PASS: Both future runtime roles remain NOLOGIN.'

# Statistics for more representative first-use queries.
for db in opsflow opsflow_incidents; do
  pgclient vacuumdb --analyze-only --dbname "$db"
done

# Do not retain the RDS master password file after this script exits.
# Keep encrypted archive copies temporarily for investigation until signoff.
touch "$workdir/verified-restore-complete"
echo 'PASS: Phase 12.5 data restore, row counts, Alembic revisions and NOLOGIN roles.'
echo 'NEXT: Remove temporary S3 objects, EC2 master-secret permissions and migration files.'
