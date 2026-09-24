# OpsFlow — PostgreSQL 18.6 migration to private RDS

## Exact deployed architecture assumed

- Existing Terraform resources: `aws_instance.live_ec2`, `aws_iam_role.live_ec2`, `aws_db_instance.live_postgres`, existing security groups.
- Existing RDS master user: `opsflow_admin` (password managed by RDS Secrets Manager).
- Existing source PostgreSQL service: `db`, PostgreSQL `18.6`.
- Source databases: `opsflow` and `opsflow_incidents` ONLY. Test databases are not copied.
- Deployment host: one AL2023 EC2 host running Docker and Systems Manager.
- Local environment: Windows + Git Bash. **Never pass Linux absolute Docker paths through Git Bash.**

## Contents

- `infrastructure/terraform/live_migration_TEMPORARY.tf`: encrypted private staging bucket and **temporary** EC2 S3-read + single-secret-read permission. Do NOT commit. Remove it and apply the cleanup plan once restore is validated.
- `scripts/deployment/phase12_5/table_counts.sql`: exact per-user-table counts, with no user data.
- `scripts/deployment/phase12_5/prepare_source.sh`: create fresh dumps/row counts/revision manifests after local writers are stopped.
- `scripts/deployment/phase12_5/restore_ec2.sh`: execute on EC2 (via SSM) as root. Checks S3 archive hashes, retrieves master secret without echoing it, verifies TLS and empty targets, restores both databases, compares every user-table count and Alembic revision, creates NOLOGIN least-privileged future application roles, and clears temporary password material.

## Critical safety rules

1. Run `terraform plan` BEFORE adding `live_migration_TEMPORARY.tf`; if the EC2 user-data update would stop/restart your recovered instance, reconcile it deliberately. Review all changes before applying anything.
2. Stop local backend, incident-service and **all** other writers to both source databases BEFORE running prepare_source.sh, and keep them stopped until live cutover. A dump is not replication. Recreate final dumps if you allow subsequent source writes.
3. Use `CONFIRM_WRITERS_STOPPED=YES bash scripts/deployment/phase12_5/prepare_source.sh` only after verifying the writers are stopped. The guard does not stop processes on your behalf.
4. No RDS public access, no inbound EC2 SSH and no `secretsmanager:GetSecretValue` wildcard. Never print master secret values in terminal, SSM Run Command parameters, logs or Git.
5. Do not rerun `restore_ec2.sh` after a partial restore: the target can contain partially restored objects. The script refuses targets already containing user tables and will not replace existing local backup files.
6. Do not run `alembic upgrade head` _before_ auditing current DB revision compatibility with repo heads. Schema migrations, credentials for runtime app roles and production secrets are Phase 12.6 activities.
7. After passing every comparison: remove S3 objects, clean local EC2 migration files, remove temporary Terraform file, review plan and apply ONLY the temporary-resource destroy. Leave RDS and EC2 intact.

## What the audit verifies

- Both full custom-format archives have matching SHA-256 checksums after transfer.
- `pg_restore --exit-on-error` succeeds on RDS 18.6.
- TLS `verify-full` is enforced with AWS RDS global CA bundle and server reports SSL in use.
- Each application table's _exact_ `COUNT(*)` and the Alembic `version_num` values match the quiesced source snapshots.
- Production runtime roles exist but are `NOLOGIN` until secrets are created in Phase 12.6.

## What this intentionally does not claim

- It does not prove application compatibility before the Phase 12.6 app tests.
- It does not create continuously synchronized replicas of local and RDS PostgreSQL.
- It does not imply one-day RDS backup retention is sufficient by itself for disaster recovery.
