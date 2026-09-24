# OpsFlow — Verified release transfer to existing EC2

**Scope:** temporary encrypted S3 transfer infrastructure, three locally built
Linux/amd64 Docker images, exact committed source, end-to-end SHA-256 checks,
noninteractive SSM release transfer, and image verification on EC2. This package
**does not** configure runtime secrets, run Alembic, start app containers, or
open an EC2 security-group port. Those are the next controlled operations.

This package was tailored to the already reviewed OpsFlow `compose.production.yaml`
services: `backend`, `incident-service`, `frontend`. The build arguments include
Python 3.13.15, Node 24, same-origin `/api/v1`, and the production NGINX site.

## Contents

```
infrastructure/terraform/live_release_transfer_TEMPORARY.tf
scripts/deployment/phase12_6/verify_release_plan.py
scripts/deployment/phase12_6/prepare_release_bundle.py
scripts/deployment/phase12_6/upload_release.py
scripts/deployment/phase12_6/prepare_receive_ssm.py
scripts/deployment/phase12_6/receive_release.sh
scripts/deployment/phase12_6/test_release_transfer.py
PHASE_12_6D_TRANSFER_README.md
```

## 1 — Install without overwriting existing source

Download the package ZIP to the repository root. In **local Windows Git Bash**:

```bash
cd ~/Documents/FullStack/opsflow
unzip -t opsflow_phase12_6d_release_transfer.zip
for file in \
  infrastructure/terraform/live_release_transfer_TEMPORARY.tf \
  scripts/deployment/phase12_6/verify_release_plan.py \
  scripts/deployment/phase12_6/prepare_release_bundle.py \
  scripts/deployment/phase12_6/upload_release.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/receive_release.sh \
  scripts/deployment/phase12_6/test_release_transfer.py \
  PHASE_12_6D_TRANSFER_README.md; do
  test ! -e "$file" || { echo "STOP: Existing file $file"; exit 1; }
done
unzip -n opsflow_phase12_6d_release_transfer.zip -d .
```

This temporary Terraform file must NOT be committed or remain in the permanent
configuration after verified launch. Exclude it locally without changing your
`.gitignore`:

```bash
grep -Fxq '/infrastructure/terraform/live_release_transfer_TEMPORARY.tf' .git/info/exclude \
  || printf '%s\n' '/infrastructure/terraform/live_release_transfer_TEMPORARY.tf' >> .git/info/exclude
git check-ignore -v infrastructure/terraform/live_release_transfer_TEMPORARY.tf
rm -f opsflow_phase12_6d_release_transfer.zip
```

## 2 — Validate and commit the permanent transfer tooling FIRST

```bash
backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 -p 'test_release_transfer.py' -v
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/prepare_release_bundle.py \
  scripts/deployment/phase12_6/upload_release.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/verify_release_plan.py
bash -n scripts/deployment/phase12_6/receive_release.sh

git add scripts/deployment/phase12_6/verify_release_plan.py \
  scripts/deployment/phase12_6/prepare_release_bundle.py \
  scripts/deployment/phase12_6/upload_release.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/receive_release.sh \
  scripts/deployment/phase12_6/test_release_transfer.py \
  PHASE_12_6D_TRANSFER_README.md

git diff --cached --check
git diff --cached --stat
git commit -m 'feat(deploy): add verified temporary EC2 release transfer tooling'
git push -u origin feature/live-deploy
git status --short
```

**Important:** Commit before creating the release archive: the build script
refuses to package uncommitted source. The release ZIP is always tied to HEAD.
Keep your final PostgreSQL backups and local writers frozen.

## 3 — Build a source archive and three Docker images LOCALLY

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_release_bundle.py --source-only
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_release_bundle.py --build-images
RELEASE_TAG="$(git rev-parse HEAD | cut -c1-12)"
ls -lh .opsflow-migration/phase12-6d/
cat .opsflow-migration/phase12-6d/SHA256SUMS
```

If you created a ZIP during earlier 12.6D.1, the script independently recreates
and compares its contents. If it differs, STOP and inspect it; it will not
silently overwrite the archive. Similarly, it refuses to overwrite an existing
Docker image archive or manifest.

The build extracts the exact committed ZIP into a temporary local directory and
builds these images for `linux/amd64`:
`opsflow-backend:<tag>`, `opsflow-incident-service:<tag>`,
`opsflow-frontend:<tag>`. Only after all builds and architecture checks pass
is a compressed `docker save` archive produced. Do not build on the 2-GiB EC2.

## 4 — Deploy the temporary transfer bucket and EC2 GetObject policy

```bash
cd infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
RDS_IDENTIFIER="$(terraform output -raw live_rds_identifier)"
RDS_CLASS="$(aws rds describe-db-instances --region "$AWS_REGION" \
  --db-instance-identifier "$RDS_IDENTIFIER" \
  --query 'DBInstances[0].DBInstanceClass' --output text)"
export TF_VAR_live_rds_instance_class="$RDS_CLASS"
terraform fmt live_release_transfer_TEMPORARY.tf
terraform fmt -check
terraform validate
rm -f phase-12-6d-transfer.tfplan
terraform plan -out=phase-12-6d-transfer.tfplan
terraform show -no-color phase-12-6d-transfer.tfplan
```

**Expected:** 6 to add, 0 to change, 0 to destroy. **Do not trust the count
alone.** Run the exact-resource guard:

```bash
set -o pipefail
terraform show -json phase-12-6d-transfer.tfplan \
  | ../../backend/.venv/Scripts/python.exe \
      ../../scripts/deployment/phase12_6/verify_release_plan.py create
```

Only when it PASSes:

```bash
terraform apply phase-12-6d-transfer.tfplan
rm -f phase-12-6d-transfer.tfplan
RELEASE_BUCKET="$(terraform output -raw live_release_transfer_bucket)"
aws s3api get-public-access-block --bucket "$RELEASE_BUCKET" --region "$AWS_REGION"
aws s3api get-bucket-encryption --bucket "$RELEASE_BUCKET" --region "$AWS_REGION" \
  --query 'ServerSideEncryptionConfiguration.Rules[].ApplyServerSideEncryptionByDefault.SSEAlgorithm' \
  --output text
```

All four block-public-access values must be true; SSE algorithm `AES256`.
This creates _temporary_ storage and IAM rights only; existing EC2/RDS/ALB
resources must remain unchanged. S3 requests must use HTTPS by bucket policy.

## 5 — Upload release artifacts from Windows

```bash
cd ../..
export AWS_REGION RELEASE_BUCKET
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/upload_release.py
RELEASE_TAG="$(git rev-parse HEAD | cut -c1-12)"
aws s3 ls "s3://$RELEASE_BUCKET/releases/$RELEASE_TAG/" --region "$AWS_REGION"
```

Confirm exactly these five keys: source zip, image tar.gz, receive_release.sh,
SHA256SUMS, and release.json. The Python uploader rejects an existing prefix
and checks file hashes before uploading. If it partially fails, inspect the
prefix and do **not** blindly rerun or overwrite.

## 6 — Transfer and verify the release via SSM Run Command

Use the existing `INSTANCE_ID` and `AWS_REGION` variables from step 4;
re-establish them from Terraform if using a new terminal. No SSH or Windows
Session Manager plugin is required:

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_receive_ssm.py
COMMAND_ID="$(aws ssm send-command \
  --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --comment 'OpsFlow 12.6D verified release receiver' \
  --parameters file://.opsflow-migration/phase12-6d/receive-ssm-params.json \
  --query 'Command.CommandId' --output text)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
```

This command verifies the RECEIVER script checksum before running it. The
receiver independently checks source and Docker image SHA256 values, confirms
`linux/amd64`, extracts into a private release directory, loads all three
images, then deletes the large local image tar to save EC2 disk space. It
**does not** start containers, configure secrets, or change `/opt/opsflow/current`.

Allow several minutes for downloading and loading the images. Poll the command
status using its existing ID rather than sending a second command:

```bash
aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

**Required:** `Status=Success`, `Code=0`, plus `PASS: Verified release installed`.
If `InProgress` or `Pending`, wait and poll again. If failed, STOP, retain
logs/temporary files, and inspect the first error. Do not delete the bucket.

## 7 — Independent EC2 verification, no application start

Open the browser EC2 **SSM Session Manager** terminal in `us-east-1`.
Copy `RELEASE_TAG` from your local terminal (non-secret) and set:

```bash
export RELEASE_TAG='YOUR_EXACT_12_CHARACTER_TAG'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/.receive_verified" \
  && echo 'PASS: Release marker'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/app/compose.production.yaml" \
  && echo 'PASS: Production Compose source'
for component in opsflow-backend opsflow-incident-service opsflow-frontend; do
  sudo docker image inspect --format '{{.RepoTags}} {{.Os}}/{{.Architecture}}' \
    "$component:$RELEASE_TAG"
done
sudo docker ps
sudo df -h /
```

Expected: all three images `linux/amd64`; no new running application containers.
DO NOT create `.env.production`, modify ALB/SG ingress, or start Compose yet.

## What happens next

12.6D.6 will securely populate the EC2 runtime from both restricted database
secrets, generate independent application signing secrets, securely install
service-identity keys, confirm RDS migrations, and validate Compose using the
final non-secret interpolation values. Only then start and test the three
primary containers. Optional workers wait for AWS permissions/capacity checks.

Keep this temporary bucket/policy until after successful initial live launch.
At that later cleanup: remove only the files under the verified
`releases/<tag>/` prefix; confirm bucket empty, move the temporary `.tf` file
to ignored `.opsflow-migration` storage, plan cleanup, run
`verify_release_plan.py cleanup`, then apply EXACT six deletes. Never run
`terraform destroy` for the whole stack.
