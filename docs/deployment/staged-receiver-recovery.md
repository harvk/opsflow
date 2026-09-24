# OpsFlow 12.6D.5B.2 — Staged release receiver: CRLF checksum recovery

**Scope:** Repair the second, *inside-the-receiver* checksum failure in the **original** already-uploaded release. This procedure does not rebuild images, create new AWS resources, modify S3, modify the release manifest, or touch the databases. It replaces only the **local helper used to generate the SSM command**. On EC2, the command verifies the original receiver's SHA-256, then patches a *temporary execution copy* of that receiver. It does not modify the original uploaded script or original release files.

## Why the previous fix was insufficient

The earlier `prepare_receive_ssm.py` normalized `SHA256SUMS` only to verify `receive_release.sh` *before* running it. The original `receive_release.sh` then downloads `SHA256SUMS` again and runs `sha256sum -c SHA256SUMS` *without normalization*. The latest failure (`opsflow-source-....zip\r: FAILED open or read`) occurs at that second check. The other objects have not been proven invalid; do not rebuild or re-upload them on this evidence.

## 0 — Check failed staging directory on EC2 (read-only)

Open AWS Console > EC2 > Instances > select the existing host > Connect > SSM Session Manager. No SSH or port changes.

Replace the sample tag below ONLY if the tag in your existing `.opsflow-migration/phase12-6d/release.json` is different:

```bash
export RELEASE_TAG='29b5857b88c0'
sudo find /opt/opsflow/releases -mindepth 1 -maxdepth 1 \
  -name ".incoming-${RELEASE_TAG}-*" -type d -print
sudo test ! -e "/opt/opsflow/releases/${RELEASE_TAG}" \
  && echo 'PASS: Final release not already installed'
df -h /
```

A prior `.incoming-*` directory is consistent with the failed attempt. **Preserve it until successful recovery.** If the final release directory is already present, stop: investigate it rather than running the receiver a second time.

## 1 — Install this patch on your Windows repository

Save `opsflow_phase12_6d_staged_receiver_crlf_recovery.zip` into `~/Documents/FullStack/opsflow`. In **local Git Bash**:

```bash
cd ~/Documents/FullStack/opsflow
unzip -t opsflow_phase12_6d_staged_receiver_crlf_recovery.zip
mkdir -p .opsflow-migration/phase12-6d-stage-repair
unzip -oq opsflow_phase12_6d_staged_receiver_crlf_recovery.zip \
  -d .opsflow-migration/phase12-6d-stage-repair

# Preserve the currently installed SSM helper in the ignored migration directory.
cp scripts/deployment/phase12_6/prepare_receive_ssm.py \
  .opsflow-migration/phase12-6d-stage-repair/prepare_receive_ssm.previous.py

# Install only the complete replacement/helper/test files.
cp .opsflow-migration/phase12-6d-stage-repair/scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/prepare_receive_ssm.py
cp .opsflow-migration/phase12-6d-stage-repair/scripts/deployment/phase12_6/receiver_patch.py \
  scripts/deployment/phase12_6/receiver_patch.py
cp .opsflow-migration/phase12-6d-stage-repair/scripts/deployment/phase12_6/test_receive_hotfix.py \
  scripts/deployment/phase12_6/test_receive_hotfix.py
cp .opsflow-migration/phase12-6d-stage-repair/PHASE_12_6D_5B2_STAGED_RECEIVER_CRLF_RECOVERY.md .
```

No edits to `receive_release.sh` or other existing release artifacts are required. **Do not commit the correction yet**, because your existing release is tied to the original Git HEAD.

Validate the Python files and run the regression tests:

```bash
backend/.venv/Scripts/python.exe -m py_compile \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/receiver_patch.py \
  scripts/deployment/phase12_6/test_receive_hotfix.py

backend/.venv/Scripts/python.exe -m unittest discover \
  -s scripts/deployment/phase12_6 \
  -p test_receive_hotfix.py -v
```

Five tests must pass. In particular, the tests cover normalization, byte-exact patching and fail-closed behavior.

## 2 — Restore environment and audit the original release

Still in local Git Bash:

```bash
cd ~/Documents/FullStack/opsflow/infrastructure/terraform
AWS_REGION="$(terraform output -raw aws_region)"
RELEASE_BUCKET="$(terraform output -raw live_release_transfer_bucket)"
INSTANCE_ID="$(terraform output -raw live_ec2_instance_id)"
cd ../..
export AWS_REGION RELEASE_BUCKET INSTANCE_ID

# Shows the original tag and full release commit, without changing Git HEAD.
backend/.venv/Scripts/python.exe -c \
  'import json,pathlib; m=json.loads(pathlib.Path(".opsflow-migration/phase12-6d/release.json").read_text(encoding="utf-8")); print("TAG="+m["tag"]); print("COMMIT="+m["commit"])'
git rev-parse HEAD
```

The full Git SHA must still equal `COMMIT`. If not, **stop**: do not reset Git or create a new release as a workaround.

If you installed `verify_staged_receiver.py` with the previous recovery package, re-run its **read-only** S3 verification:

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/verify_staged_receiver.py
```

Require its original manifest/S3 receiver comparisons to pass. If the diagnostic file is not available or a comparison fails, stop and preserve the error before proceeding. This hotfix is intentionally not designed to conceal damaged or mismatched S3 objects.

## 3 — Generate the one-time SSM recovery command

```bash
backend/.venv/Scripts/python.exe \
  scripts/deployment/phase12_6/prepare_receive_ssm.py

test -s .opsflow-migration/phase12-6d/receive-ssm-params.json \
  && echo 'PASS: Recovery command generated'
```

The helper verifies the local original receiver against `release.json`, computes the expected SHA-256 of the *temporary execution copy*, and embeds a non-secret patch program into the SSM command. The SSM command rechecks the original receiver downloaded from S3 against both the manifest-derived SHA-256 and `SHA256SUMS`, then checks the patched execution-copy SHA-256. Only then does it run the temporary copy.

The temporary execution copy normalizes CRLF **inside the original receiver's staging directory** before `sha256sum -c`. No file is re-uploaded to S3.

## 4 — Retry the receiver ONCE

```bash
COMMAND_ID="$(
  aws ssm send-command \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment 'OpsFlow original-release staged checksum recovery' \
    --parameters file://.opsflow-migration/phase12-6d/receive-ssm-params.json \
    --query 'Command.CommandId' \
    --output text
)"
printf 'COMMAND_ID=%s\n' "$COMMAND_ID"
```

Poll this exact command ID until finished:

```bash
aws ssm get-command-invocation \
  --region "$AWS_REGION" \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query '{Status:Status,Code:ResponseCode,Output:StandardOutputContent,Error:StandardErrorContent}' \
  --output json
```

Require `Status=Success`, `Code=0`, and `PASS: Verified release installed`. On failure, **do not resubmit**; preserve the exact output and any `.incoming-*` directory for diagnosis.

## 5 — Independently verify on EC2

Use the **original tag** from `release.json` (example below), in the EC2 browser terminal:

```bash
export RELEASE_TAG='29b5857b88c0'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/.receive_verified" \
  && echo 'PASS: Release completion marker'
sudo test -f "/opt/opsflow/releases/$RELEASE_TAG/app/compose.production.yaml" \
  && echo 'PASS: Production Compose present'
for image in opsflow-backend opsflow-incident-service opsflow-frontend; do
  sudo docker image inspect \
    --format '{{.RepoTags}} {{.Os}}/{{.Architecture}}' \
    "$image:$RELEASE_TAG"
done
sudo docker ps
df -h /
```

All images should report `linux/amd64`. The transfer must not start application containers. Keep the temporary release S3 bucket and source archives for the next runtime phase.

After success, inspect prior failed stages with `sudo find /opt/opsflow/releases -maxdepth 1 -type d -name ".incoming-${RELEASE_TAG}-*" -print`; remove only verified stale staging directories later when you are confident no transfer is running. The new release directory must be preserved.

## 6 — Commit after successful installation

On local Git Bash, review the working tree and commit the repair once the **original** release is installed:

```bash
cd ~/Documents/FullStack/opsflow
git status --short
git add \
  scripts/deployment/phase12_6/prepare_receive_ssm.py \
  scripts/deployment/phase12_6/receiver_patch.py \
  scripts/deployment/phase12_6/test_receive_hotfix.py \
  PHASE_12_6D_5B2_STAGED_RECEIVER_CRLF_RECOVERY.md

git diff --cached --check
git diff --cached --stat
git commit -m 'fix(deploy): normalize CRLF during staged release verification'
git push origin feature/live-deploy
```

If the earlier repair files are still modified or untracked, review and commit those in a separate related commit **after** the release is installed. Keep the exact original release tag recorded; the new Git HEAD will be different after these commits.

**Next:** Phase 12.6D.6 — production runtime configuration and secrets. Do not run release-transfer Terraform cleanup or open EC2 application ingress yet.
