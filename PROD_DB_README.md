# OpsFlow: First production database logins

**Scope:** only two Secrets Manager secret metadata resources, permanent EC2
read permission for those two secrets, a **temporary** permission to read the
RDS-managed master secret and initialize the two secret values, plus an
idempotent one-time role-bootstrap script executed through Systems Manager.

No application containers are launched. No RDS data or schema is migrated,
dropped, or rebuilt. No EC2 or RDS resource is replaced. The completed
production application configuration and runtime isolation follow in 12.6C.

## Source-grounded assumptions

- `aws_db_instance.live_postgres` exists; `master_user_secret[0].secret_arn`
  names its RDS-managed master secret.
- `aws_iam_role.live_ec2` is the existing instance role.
- `local.live_name_prefix` and `local.live_common_tags` exist in
  `live_network.tf`.
- Phase 12.5 created the `opsflow_app` and `opsflow_incidents_app` NOLOGIN
  privilege roles. The script checks them before changing anything.
- Both RDS DBs were independently verified after restoring Phase 12.5 dumps.
- EC2 supports SSM, AWS CLI, Docker, Python3, and outbound access to AWS APIs
  and the official RDS CA bundle. The RDS security group admits TCP 5432
  from EC2's security group.

## Placement

Extract this package **into the repository root**. Use `unzip -n` to avoid
silently replacing existing files. The `live_db_bootstrap_TEMPORARY.tf` file is
for this phase only, not a permanent source change. Add it to local
`.git/info/exclude`, NOT your tracked `.gitignore`.

## Before Terraform

1. Check `git status --short`, current branch `feature/live-deploy`, existing
   Terraform no-op baseline, EC2 online, RDS available, and migrated data.
2. From `infrastructure/terraform`, set the required existing instance class:
   `export TF_VAR_live_rds_instance_class="$(aws rds describe-db-instances --region "$(terraform output -raw aws_region)" --db-instance-identifier "$(terraform output -raw live_rds_identifier)" --query 'DBInstances[0].DBInstanceClass' --output text)"`
3. Format and validate, then produce `terraform plan -out=phase-12-6b.tfplan`.
4. **Expected creation set** (after reading the plan):
   - `aws_secretsmanager_secret.live_core_db_login`
   - `aws_secretsmanager_secret.live_incident_db_login`
   - `aws_iam_role_policy.live_runtime_db_secret_read`
   - `aws_iam_role_policy.live_db_bootstrap_temp`
     No changes/deletes of other resources.
5. Apply the reviewed saved plan. These two secret resources have _no values_
   until the bootstrap script succeeds.

## Generate + send non-secret bootstrap command

From repository root in Windows Git Bash:

```
backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_db_bootstrap_ssm.py
```

With `AWS_REGION` and `INSTANCE_ID` set from existing Terraform outputs:

```
COMMAND_ID="$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'OpsFlow Phase 12.6B restricted DB logins' \
  --parameters file://.opsflow-migration/phase12-6b-ssm-params.json \
  --query 'Command.CommandId' --output text)"
aws ssm wait command-executed --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

The script writes passwords only into process memory, AWS Secrets Manager,
and a short-lived root-owned `/dev/shm` working directory. It uses verified
RDS TLS via `sslmode=verify-full`. No master password appears in SSM command
parameters or the logs. It tests each login against its own database and
ensures it **cannot** connect to the other database.

**Stop on failures**. An interrupted bootstrap might leave some resources
initialized. Its marker at `/opt/opsflow/.phase12-6b-started` permits careful
retries using existing secret versions, but inspect the first error before
retrying. If `/opt/opsflow/.phase12-6b-verified` exists, the script refuses
rotation and exits successfully.

## Immediately remove temporary master-secret access

Once SSM reports `Success` / exit `0`, and its output contains
`PASS: 12.6B database bootstrap verified`:

1. On local machine, move `live_db_bootstrap_TEMPORARY.tf` to an **ignored**
   backup outside `infrastructure/terraform/` (e.g. `.opsflow-migration/`).
2. Run `terraform validate`, then save and review a NEW Terraform cleanup plan.
   It must propose **only** deletion of `aws_iam_role_policy.live_db_bootstrap_temp`.
3. Apply that reviewed plan and verify `terraform plan` reports **No changes**.
4. Audit `aws iam list-role-policies` for the EC2 role to verify its
   `opsflow-dev-db-bootstrap-temp` inline policy is absent.
5. You may then remove the ignored temporary backup and the generated SSM
   parameter file. Keep the permanent Terraform file, Python scripts and tests.

No Terraform-managed resource ever contains a generated database password.
Secrets Manager `PutSecretValue` is invoked on EC2, not by Terraform.

## Security model

These privileges are isolated across the **two PostgreSQL databases**. The
single EC2 host uses one instance IAM role for all containers, so it can read
**both** app secrets. Per-container IAM isolation would require a different
workload-identity architecture (e.g. ECS task roles) in a future phase. Keep
this single-host limitation explicit in your portfolio documentation.

The script revokes default database `CONNECT` privilege from PUBLIC for both
OpsFlow databases, then relies on the Phase 12.5 NOLOGIN group grants and
PG18 inherited role memberships to authorize the corresponding logins.

**No test database is created in production.** The current backend settings
module _requires_ `TEST_DATABASE_URL`, which is a code-level production
configuration defect to address in 12.6C before running the backend.

## Phase 12.6C code audit (from uploaded source, not assumptions)

Do not launch the existing local `compose.yaml` unchanged against RDS:

- `db`, `provision-databases`, `migrate` and `incident-migrate` are designed
  for the local PostgreSQL Docker container and also migrate test databases.
  A separate production Compose configuration must omit the local database
  and provisioning service and verify restored Alembic heads before startup.
- `backend/app/core/config.py` currently requires `test_database_url` even
  though production has NO test DB. Resolve that application configuration
  explicitly (and run existing tests) instead of inventing an RDS test DB.
- `frontend/src/api/apiClient.ts` has a `localhost:8000` API fallback, and
  `frontend/nginx/default.conf` currently serves static assets only. The
  production frontend requires a same-origin API routing strategy and a
  properly configured Vite build BEFORE traffic reaches it through ALB.
- `compose.aws-local.yaml` is explicitly local-only, mounts workstation AWS
  credentials, and defines the three incident-background workers. The
  production deployment must recreate those workers without mounting local
  credential directories; the EC2 role needs narrowly scoped SQS/DynamoDB
  permissions based on each worker's source code.
- Service identity requires distinct private/public keys mounted into each
  Python service. Never reuse a private key accidentally included in an
  exported archive as a general production secret; generate and distribute
  deployment identities deliberately.
- The `t3.small` has 2 GiB RAM. Build large Docker images off-server in
  Phase 12.6C or measure resources before attempting simultaneous builds.

The database bootstrap is a separate checkpoint. Stage 12.6C will deliver
source-based production application changes and launch instructions AFTER the
restricted login setup verifies successfully.
