# Production runtime setup

OpsFlow's production runtime preparation is deliberately separate from release transfer, Terraform, migration, and application startup. It uses the **original release tag from the signed-off local `release.json`**, not the latest Git HEAD (which may contain deployment-tooling corrections).

## Scope and safeguards

- `inspect`: read-only gate: existing verified release and all three preloaded Linux/amd64 images.
- `stage`: uses the EC2 instance role to read **only the two runtime RDS secrets**; downloads the AWS RDS CA bundle; creates persistent, separate production service-identity RSA-3072 keypairs and six independent application signing keys **on EC2**; validates both databases over `sslmode=verify-full`, verifies database user and SSL session, and compares **actual RDS Alembic revisions to migration heads from the exact preloaded images**. It performs no DDL and starts no app services.
- `configure`: requires the actual intended HTTPS application origin and an SES-verified sender. It creates root-protected per-release environment files, service-key files, CA material and a small Compose override adding the trust bundle to core, incident and optional workers. `docker compose config --quiet` is run without displaying expanded secrets. It **does not start containers**.

Existing signing keys and files are never silently overwritten or rotated. A conflicting file or partially generated keypair is a hard stop. EC2 shared signing keys live under `/opt/opsflow/shared` (root-only parent); per-release Compose secret files are read-only and mounted only into the services that need them. Preserve secure off-instance backup of the shared keys before relying on the application for real users. New production signing keys intentionally invalidate development-signed sessions; user accounts and password hashes remain in PostgreSQL.

The downloaded trust bundle is checked for PEM boundaries, stored locally, and used in genuine TLS `verify-full` connections. A certificate or migration-head mismatch blocks deployment. If rotating the CA or signing keys in the future, use a separate documented rotation procedure; this installer does not do it automatically.

**Precondition:** the prior Systems Manager release transfer has actually returned `Success`, code `0` and the `PASS: Verified release installed` message. If you cannot confirm that, DO NOT execute `stage` or `configure`. Finish the release receiver recovery first. Terraform output verification or local offline tests do not prove successful installation on EC2.

## Install and validate locally (Windows Git Bash)

From `~/Documents/FullStack/opsflow`:

```bash
unzip -t opsflow_production_runtime_setup.zip
for file in \
  compose.runtime.yaml \
  scripts/deployment/phase12_6/prepare_runtime_ssm.py \
  scripts/deployment/phase12_6/stage_production_runtime.py \
  scripts/deployment/phase12_6/test_runtime_setup.py \
  docs/deployment/production-runtime-setup.md
do
  if test -e "$file"; then echo "STOP: existing path $file"; exit 1; fi
done
unzip -n opsflow_production_runtime_setup.zip -d .
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/prepare_runtime_ssm.py \
  scripts/deployment/phase12_6/stage_production_runtime.py \
  scripts/deployment/phase12_6/test_runtime_setup.py
backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 -p test_runtime_setup.py -v
```

The tests use the standard Python library only and **do not start Bash from Windows Python**, call AWS, create Windows temporary directories, or start Docker.

Do not commit or rebuild the original release simply to change the runtime tooling. Keep `feature/live-deploy` on the branch you are developing. The local helper always uses the **manifest's original release tag** rather than Git HEAD.

## Identify release and initialize non-secret inputs

From the repository root:

```bash
backend/.venv/Scripts/python.exe -c 'import json,pathlib; m=json.loads(pathlib.Path(".opsflow-migration/phase12-6d/release.json").read_text()); print("Original release tag:",m["tag"]); print("Original commit:",m["commit"])'
backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_runtime_ssm.py --init
```

The helper calls `terraform output -json` inside `infrastructure/terraform` and creates only:

`.opsflow-migration/phase12-6d/runtime-inputs.json`

This is a non-secret configuration file. **It is ignored by Git** along with `.opsflow-migration/`. The helper does not read `.env`, private key files or the RDS master secret. It will not overwrite existing inputs. `frontend_origin` and `ses_from_email` deliberately start empty.

If Terraform output names are missing, STOP rather than inventing values. Never use the RDS master secret ARN in this input file.

## Check the existing release remotely without modifying it

Restore environment identifiers **locally** from Terraform:

```bash
cd infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
cd ../..
```

Generate and send the read-only command:

```bash
backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_runtime_ssm.py --mode inspect
COMMAND_ID="$(aws ssm send-command --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript --comment 'OpsFlow verified release inspection' \
  --parameters file://.opsflow-migration/phase12-6d/runtime-inspect-ssm-params.json \
  --query 'Command.CommandId' --output text)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
aws ssm wait command-executed --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

You **must see `Success`, `Code=0`, and `PASS: Original release and all three Linux/amd64 images installed`**. If not, stop. The script checks the installed release marker, manifest, production Compose file and three image architectures. It doesn't trust a clean Terraform plan as proof of transfer.

If SSM's wait command fails, inspect the existing command ID; do not immediately submit a duplicate.

## Stage production keys and verify both RDS databases

This operation writes new production-only cryptographic material to EC2 shared storage; review the preflight before using it:

```bash
backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_runtime_ssm.py --mode stage
COMMAND_ID="$(aws ssm send-command --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript --comment 'OpsFlow stage production runtime and check RDS' \
  --parameters file://.opsflow-migration/phase12-6d/runtime-stage-ssm-params.json \
  --query 'Command.CommandId' --output text)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
aws ssm wait command-executed --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

The stage command requires EC2 `aws`, `docker`, `openssl` and network access to the RDS CA endpoint. If OpenSSL is missing, connect through SSM and install it using `sudo dnf install -y openssl` after verifying the package source.

Expected success messages include read-only RDS TLS/SQL and Alembic head checks for **both** `opsflow` and `opsflow_incidents`, then `PASS: Persistent signing keys, service identities and verified RDS connections staged`.

If the database check fails, **do not run `alembic upgrade`**. Inspect the migration state and source/release relationship. Stage never modifies the restored data. Inspect the same SSM command's failure, then reconcile the specific error before any retry. A repeat execution uses existing keys without rotating them.

## Configure the production Compose runtime (requires real origin and verified sender)

The initial stage above is useful even if you haven't chosen the domain yet. You **cannot finish runtime configuration** with `localhost`, `example.com` or a placeholder domain because real production cookie, CORS and password-reset flows need a stable HTTPS origin. Your verified sender should correspond to an approved SES identity; check sender verification in the AWS Console or with SESv2 before configuring.

Open only the ignored non-secret input JSON in VS Code:

```bash
code .opsflow-migration/phase12-6d/runtime-inputs.json
```

Replace the blank values with your **actual intended** `frontend_origin` and **SES-verified** `ses_from_email`. Example format (not deployment values): `https://app.YOUR-OWN-DOMAIN` and `no-reply@YOUR-OWN-DOMAIN`. Do not place any passwords, JWT keys, AWS access keys or private PEM data in this file.

Then:

```bash
backend/.venv/Scripts/python.exe scripts/deployment/phase12_6/prepare_runtime_ssm.py --mode configure
COMMAND_ID="$(aws ssm send-command --region "$AWS_REGION" --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript --comment 'OpsFlow prepare private production Compose runtime' \
  --parameters file://.opsflow-migration/phase12-6d/runtime-configure-ssm-params.json \
  --query 'Command.CommandId' --output text)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
aws ssm wait command-executed --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws ssm get-command-invocation --region "$AWS_REGION" --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

Expected: `Success` and `PASS: Production runtime files prepared and Docker Compose configuration validated`.

**Never print or upload** `.env.production`, `.opsflow-runtime/*.env`, `/opt/opsflow/shared/secrets/*` or Docker Compose's fully expanded config. Use only `docker compose ... config --quiet` when checking it.

## EC2 read-only completion check

In EC2 Session Manager, enter the **actual original** release tag from your local manifest (do not use the latest Git HEAD):

```bash
RELEASE_TAG='REPLACE_WITH_ORIGINAL_RELEASE_TAG'
APP="/opt/opsflow/releases/$RELEASE_TAG/app"
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/.receive_verified" && echo 'PASS: Release marker'
sudo test -f /opt/opsflow/shared/runtime-staged && echo 'PASS: Restricted RDS SQL verified'
sudo test -f "$APP/.opsflow-runtime/runtime-configured" && echo 'PASS: Compose runtime ready'
sudo test -f "$APP/.opsflow-runtime/certs/global-bundle.pem" && echo 'PASS: RDS CA mounted source ready'
sudo test -f "$APP/compose.runtime.yaml" && echo 'PASS: Certificate override installed'
sudo test -f "$APP/.env.production" && echo 'PASS: Production interpolations available'
sudo docker ps
```

`sudo docker ps` should show **no OpsFlow production containers yet**. We have neither opened EC2 ingress nor enabled the optional background workers. Do not print your environment files or private keys to verify them.

## Next deployment stage

Only after both database-head checks and runtime files pass, begin the separate **production application startup** step. Before enabling incident management and email operations, audit your EC2 IAM role for scoped `sqs:SendMessage`, the required SES sending actions and any worker-specific AWS permissions. Neither this package nor Phase 12.6B adds those capabilities automatically. The ALB/HTTPS configuration follows separately, with traffic permitted from its security group rather than directly from the internet.

Cleanup: the SSM helper under `/tmp/opsflow-runtime-helper` contains scripts and non-secret inputs; it can be removed after successful validation. The real EC2 `/opt/opsflow/shared` directory and your original local database backup archives are long-lived and **must be preserved**.

Source review reference: this installer targets your audited production Compose layout, the two `NOLOGIN` privilege groups with restricted `opsflow_core_login` / `opsflow_incidents_login` members, SQLAlchemy with psycopg 3, and the two Alembic migration trees built into your deployed Docker images. No AWS or container actions were performed when preparing this package.
