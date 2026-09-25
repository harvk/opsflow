#!/bin/bash
# First-boot host bootstrap (no secrets).
# AWS cloud-init launches this as root. Logs:
#   /var/log/opsflow-bootstrap.log
#   /var/log/cloud-init-output.log
set -Eeuo pipefail
exec > >(tee -a /var/log/opsflow-bootstrap.log) 2>&1
trap 'echo "[OpsFlow] Bootstrap failed on line ${LINENO}" >&2' ERR

echo '[OpsFlow] Installing Docker and baseline tools'
# AL2023 includes curl-minimal by default. Installing the full curl
# package alongside it can cause a DNF dependency conflict.
dnf install -y docker git jq
if ! command -v curl >/dev/null 2>&1; then
  dnf install -y curl-minimal
fi

systemctl enable --now docker
systemctl enable --now amazon-ssm-agent

# Restrict application working directory until deployment in Phase 12.6.
# Administrative SSM sessions use sudo; no SSH, no docker-group membership.
install -d -o ec2-user -g ec2-user -m 0750 /opt/opsflow

docker --version
systemctl is-active docker
systemctl is-active amazon-ssm-agent

touch /opt/opsflow/bootstrap-complete
chown ec2-user:ec2-user /opt/opsflow/bootstrap-complete
chmod 0640 /opt/opsflow/bootstrap-complete

echo '[OpsFlow] Phase 12.4 host bootstrap complete'
