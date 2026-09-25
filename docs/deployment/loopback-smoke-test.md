# Loopback-only deployment smoke test

## Why this exists

The OpsFlow production runtime requires a *real HTTPS application origin* and an
Amazon SES-verified sender. Neither is required to confirm that the already-built
containers, service-identity files and private RDS connectivity work on EC2.
Keep this preview entirely on the existing `127.0.0.1:8080` host binding while
DNS, ALB, TLS and verified email identity are configured independently.

The preview does **not** enable verified email sending and must not receive real
users. `disabled@example.invalid` is an intentional non-deliverable sender
configuration, not an SES identity or a claim that password-reset emails work.
Do not test the password-reset/email flow in preview; validate it only after the
real sender and HTTPS origin have been configured and permissions audited.

## Prerequisite

The release inspection and runtime `stage` operation must already have reported
success for the original release tag (not the latest Git `HEAD`). `stage` must
have verified the restricted RDS credentials, certificate-verified TLS, both
Alembic heads, and persistent signing/service-identity keys.

## Install and test the patch (local Windows Git Bash)

From the repository root, extract the package to
`.opsflow-migration/runtime-preview-patch/` and run:

```bash
backend/.venv/Scripts/python.exe \
  .opsflow-migration/runtime-preview-patch/install_preview_patch.py
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/prepare_runtime_ssm.py \
  scripts/deployment/phase12_6/stage_production_runtime.py \
  scripts/deployment/phase12_6/test_runtime_setup.py
backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 -p test_runtime_setup.py -v
```

All 14 tests should pass. These tests are pure Python and do not start Linux
Bash from Windows Python.

## Prepare and run preview configuration (local Git Bash)

Do **not** edit `runtime-inputs.json` to invent a domain or sender. Leave the
existing blank `frontend_origin` and `ses_from_email` values intact.

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_runtime_ssm.py --mode preview

cd infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
cd ../..

COMMAND_ID="$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'OpsFlow private loopback preview configuration' \
  --parameters file://.opsflow-migration/phase12-6d/runtime-preview-ssm-params.json \
  --query 'Command.CommandId' --output text)"

printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
aws ssm wait command-executed \
  --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID"
aws ssm get-command-invocation \
  --region "$AWS_REGION" --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

Expected output: `PASS: Loopback preview Compose validated; SES and public HTTPS NOT configured`.
This phase does **not** start any containers or change Terraform.

## Verify safely on EC2 (browser SSM session)

Set the original release tag from the local `release.json`, not from `git HEAD`:

```bash
RELEASE_TAG='YOUR_ORIGINAL_RELEASE_TAG'
APP="/opt/opsflow/releases/$RELEASE_TAG/app"
sudo test -f /opt/opsflow/shared/runtime-staged && echo 'PASS: Staged RDS credentials/keys retained'
sudo test -f "$APP/.opsflow-runtime/runtime-preview-configured" && echo 'PASS: Preview Compose verified'
sudo test -f "$APP/.env.preview" && echo 'PASS: Private preview env exists'
sudo test ! -f "$APP/.opsflow-runtime/runtime-configured" && echo 'Production has not been configured yet'
```

Do not `cat` the private environment files or use a verbose Compose config
that could expose them. The later startup step must use **only** the preview
environment for private smoke tests, for example `docker compose --env-file
.env.preview -f compose.production.yaml -f compose.runtime.yaml config --quiet`.
Do not switch to public inbound rules or ALB traffic while preview values are
in use.

## Transition to actual production

Once you own an HTTPS domain and have an SES-verified sending identity in the
same AWS Region, update only the nonsecret `frontend_origin` and
`ses_from_email` fields in the ignored `runtime-inputs.json`, then generate
`--mode configure`. The strict production validator is unchanged and creates a
**separate** `.env.production` and `runtime-configured` marker without
replacing `.env.preview`, rotating keys or modifying the migrated databases.
Remove or disable preview deployments before opening any application ingress.
