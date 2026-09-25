# OpsFlow Phase 12.6D.5B — Release receiver checksum recovery

**Goal:** Retry the existing, already-uploaded release after the initial SSM transfer failed *before the receiver ran*. Keep the same Git release commit, the same S3 release prefix, the same `release.json`, and the same uploaded images. Do **not** rebuild, re-upload, replace Terraform resources, or create another EC2 instance as part of this repair.

## What failed

The original `prepare_release_bundle.py` wrote `SHA256SUMS` with text-mode platform newlines. Windows text output used CRLF (`\r\n`). The original SSM command ran `awk '$2 == "receive_release.sh" {print $1}'` on the downloaded checksum list. In that context, the second field can be `receive_release.sh\r`, so the lookup returned no hash and printed `FAIL: Receiver checksum mismatch`. The observed S3 `SHA256SUMS` size of 287 bytes is consistent with the three required entries in CRLF (the corresponding LF-only file would be 284 bytes). This is a **likely root cause**, not proof that the S3 file's bytes are correct; verify them before retrying.

`prepare_receive_ssm.py` now removes carriage returns *when reading the existing checksum file for verification*, without changing or replacing the uploaded release. `prepare_release_bundle.py` now writes LF-only checksum files for **future** releases and uses explicit optional-stream narrowing to address Pylance. `test_release_transfer.py` guards its dynamic module import to address Pylance and includes regression tests. New `verify_staged_receiver.py` verifies the **existing** S3 receiver and checksum entry against the existing local manifest and receiver before retrying.

**Important:** Do not commit these changes before successfully installing the already-uploaded release. The existing manifest and receiver helper select the release by `git HEAD`. Committing creates a different HEAD and release tag.

## 1. Stage and install the complete corrected files (Windows Git Bash)

Download `opsflow_phase12_6d_receiver_checksum_repair.zip` to the repository root.

```bash
cd ~/Documents/FullStack/opsflow
unzip -t opsflow_phase12_6d_receiver_checksum_repair.zip
mkdir -p .opsflow-migration/phase12-6d-checksum-fix
unzip -oq opsflow_phase12_6d_receiver_checksum_repair.zip \
  -d .opsflow-migration/phase12-6d-checksum-fix

for name in prepare_release_bundle.py prepare_receive_ssm.py test_release_transfer.py verify_staged_receiver.py; do
  cp ".opsflow-migration/phase12-6d-checksum-fix/scripts/deployment/phase12_6/$name" \
    "scripts/deployment/phase12_6/$name"
done
cp .opsflow-migration/phase12-6d-checksum-fix/PHASE_12_6D_5B_RELEASE_CHECKSUM_RECOVERY.md .
```

These files contain the complete implementations. **Do not paste Python code into Git Bash** or manually edit the previously uploaded `receive_release.sh`.

## 2. Verify the fix offline

```bash
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/prepare_release_bundle.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/test_release_transfer.py \
  scripts/deployment/phase12_6/verify_staged_receiver.py

backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 -p test_release_transfer.py -v

git status --short
```

All six offline tests must pass. Modified/untracked files are expected **temporarily**; do not commit until the existing release is installed.

## 3. Restore the exact active infrastructure values

```bash
cd infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
RELEASE_BUCKET="$(terraform output -raw live_release_transfer_bucket)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
cd ../..
export AWS_REGION RELEASE_BUCKET INSTANCE_ID

backend/.venv/Scripts/python.exe -c \
  'import json,pathlib; j=json.loads(pathlib.Path(".opsflow-migration/phase12-6d/release.json").read_text());print("RELEASE_TAG="+j["tag"]);print("RELEASE_COMMIT="+j["commit"])'

git rev-parse HEAD
```

The full Git HEAD must equal `RELEASE_COMMIT` in `release.json`. **If it doesn't, stop**: do not re-upload or change the release tag to work around it.

## 4. Audit the existing S3 release (read-only)

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/verify_staged_receiver.py
```

Require all three `Manifest/...` checks and the final `PASS` message. The script downloads only the already-uploaded receiver and checksum list to a temporary local directory; it **does not modify S3**. A CRLF line count greater than zero supports the suspected original cause. Any mismatch is a stop condition requiring separate investigation.

## 5. Regenerate only the SSM command

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_receive_ssm.py

grep -n 'tr -d' .opsflow-migration/phase12-6d/receive-ssm-params.json
```

The generated command should contain `tr -d` to normalize the downloaded checksum list during lookup. Do not regenerate the release artifacts, Docker images, or uploader payload.

## 6. Retry the transfer once

```bash
COMMAND_ID="$(
  aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment 'OpsFlow 12.6D receiver CRLF-safe checksum recovery' \
    --parameters file://.opsflow-migration/phase12-6d/receive-ssm-params.json \
    --query 'Command.CommandId' --output text
)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"

aws ssm get-command-invocation \
  --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

If status is `Pending` or `InProgress`, poll using the **same** command ID. Require `Success`, response code `0`, and `PASS: Verified release installed`. If it fails again, capture both standard output and standard error, **do not resubmit**. Especially do not remove a partial `.incoming-*` directory before investigating the new error.

## 7. Verify inside EC2 via browser Session Manager

Copy the original `RELEASE_TAG` from Step 3 (not a tag after any new commit):

```bash
export RELEASE_TAG='REPLACE_WITH_ORIGINAL_12_CHARACTER_RELEASE_TAG'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/.receive_verified" \
  && echo 'PASS: Release installed'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/app/compose.production.yaml" \
  && echo 'PASS: Production Compose source installed'

for image in opsflow-backend opsflow-incident-service opsflow-frontend; do
  sudo docker image inspect --format '{{.RepoTags}} {{.Os}}/{{.Architecture}}' \
    "$image:$RELEASE_TAG"
done

df -h /
sudo docker ps
```

All three images must be `linux/amd64`. No production containers should be started by this transfer step.

## 8. Commit the recovered tooling **after successful transfer**

From local Git Bash at the repository root:

```bash
git add \
  scripts/deployment/phase12_6/prepare_release_bundle.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/test_release_transfer.py \
  scripts/deployment/phase12_6/verify_staged_receiver.py \
  PHASE_12_6D_5B_RELEASE_CHECKSUM_RECOVERY.md

git diff --cached --check
git diff --cached --stat
git commit -m 'fix(deploy): normalize Windows release checksum verification'
git push origin feature/live-deploy
```

Keep the staging bucket and original release artifacts until production containers are configured and proven healthy in the next subphase. Do not run Terraform cleanup yet.
