# Production runtime preflight

This procedure follows the verified EC2 release receiver. It tests the **original** release tag from `.opsflow-migration/phase12-6d/release.json` and never assumes that current Git HEAD still points to that release after the receiver hotfixes.

The scripts are read-only: they do not write RDS, change Terraform, generate credentials, run Alembic, create runtime environment files or start Docker containers. All retrievals of application database secrets happen in memory on EC2; only their non-sensitive metadata is validated.

## Preconditions

- AWS Systems Manager receiver returned `Success`, response code `0`, and `PASS: Verified release installed`.
- EC2 browser terminal confirms `/opt/opsflow/releases/<original-tag>/.receive_verified` and `app/compose.production.yaml` exist.
- Both database Secrets Manager versions are still `AWSCURRENT`; temporary master-secret bootstrap policy has been deleted.
- Original local PostgreSQL backup archives are retained and local writers remain stopped.

If the receiver command has not yet succeeded, **do not advance** to runtime configuration. Inspect its existing command ID and preserve the S3 bucket and partial EC2 staging directories.

## Install on Windows (Git Bash)

From `~/Documents/FullStack/opsflow`, save `opsflow_production_runtime_preflight.zip` in the repository root and run:

```bash
unzip -t opsflow_production_runtime_preflight.zip
for f in \
  scripts/deployment/phase12_6/check_ec2_release.py \
  scripts/deployment/phase12_6/prepare_runtime_preflight_ssm.py \
  scripts/deployment/phase12_6/test_runtime_preflight.py \
  docs/deployment/production-runtime-preflight.md; do
  if [ -e "$f" ]; then echo "STOP: $f already exists"; exit 1; fi
done
unzip -n opsflow_production_runtime_preflight.zip -d .
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/check_ec2_release.py \
  scripts/deployment/phase12_6/prepare_runtime_preflight_ssm.py \
  scripts/deployment/phase12_6/test_runtime_preflight.py
backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 -p test_runtime_preflight.py -v
rm -f opsflow_production_runtime_preflight.zip
```

Native Windows Python runs all six tests **without launching Git Bash** and without subprocess-based filesystem cleanup. This avoids the earlier locked Windows temp-directory failure.

## Generate a non-secret preflight command

Run in the local repository root:

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_runtime_preflight_ssm.py
```

This resolves `AWS_REGION`, the existing EC2 instance profile name, two runtime database secret ARNs, and the private RDS hostname using the **current Terraform outputs**. It reads the **original** release tag from the saved local release manifest instead of guessing from Git HEAD. It writes the non-secret SSM parameters file under the ignored `.opsflow-migration/phase12-6d/` directory.

## Execute once using the original EC2 instance

In local Git Bash:

```bash
cd infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
cd ../..

COMMAND_ID="$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment "OpsFlow read-only production runtime preflight" \
  --parameters file://.opsflow-migration/phase12-6d/runtime-preflight-ssm-params.json \
  --query Command.CommandId --output text)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
```

Poll **the same command** until it completes:

```bash
aws ssm get-command-invocation \
  --region "$AWS_REGION" --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

Do not start a second command when the status is `Pending` or `InProgress`. On `Failed`, retain all output and stop.

## Expected gates

- Original receive marker, release manifest, original receiver checksum, source ZIP checksum and ZIP integrity match.
- The three exact Docker images for the original release tag exist and are `linux/amd64`.
- The SSM execution uses the intended EC2 IAM role.
- EC2 can retrieve both runtime secrets and the metadata matches the expected restricted login and private RDS host; **no secret value is printed**.
- EC2 can establish a TCP connection to the private RDS host on port 5432. **This does not prove TLS or SQL credentials yet.**
- At least 4 GiB remains available on the EC2 root disk.
- No OpsFlow production containers were started by this verification.

The last line is `PASS: Release and secret-access preflight complete; no containers started`.

## What comes next

After the preflight passes, proceed with controlled production runtime preparation: verify the RDS CA certificate and restricted login SQL connections using `sslmode=verify-full`; compare both live Alembic revisions to the heads in the **installed** release without performing upgrades; generate unique production application secrets and service-identity keypairs; verify file and Docker Compose permissions and then launch only the three primary services. The existing Compose file needs an RDS CA file mount before a `verify-full` application connection can succeed; do not invent runtime environment values or copy local development keys.

Do not remove the temporary release-transfer bucket before the production startup and recovery checks complete. Do not commit `release.json`, `.env.production`, RDS passwords, private keys, original database archives, Terraform state or the generated SSM parameters. Documentation is intentionally named by **subject**, not by phase number.
