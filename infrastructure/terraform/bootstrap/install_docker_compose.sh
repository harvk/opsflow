#!/bin/bash
# OpsFlow Phase 12.4: run via AWS Systems Manager Run Command as root.
# Official, pinned Docker Compose binary; verifies the published SHA256.
set -Eeuo pipefail

COMPOSE_VERSION="v5.5.0"
ARCH="$(uname -m)"
if [ "$ARCH" != "x86_64" ]; then
  echo "Unexpected EC2 architecture: $ARCH (expected x86_64)" >&2
  exit 1
fi

RELEASE="https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}"
ASSET="docker-compose-linux-${ARCH}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

curl -fSL --retry 3 "${RELEASE}/${ASSET}" -o "${TMPDIR}/${ASSET}"
curl -fSL --retry 3 "${RELEASE}/${ASSET}.sha256" -o "${TMPDIR}/${ASSET}.sha256"

EXPECTED="$(awk 'NR==1 {print $1}' "${TMPDIR}/${ASSET}.sha256")"
if ! [[ "$EXPECTED" =~ ^[0-9a-fA-F]{64}$ ]]; then
  echo 'The published Compose checksum did not contain a valid SHA256.' >&2
  exit 1
fi
printf '%s  %s\n' "$EXPECTED" "${TMPDIR}/${ASSET}" | sha256sum --check --status

install -d -m 0755 /usr/local/lib/docker/cli-plugins
install -o root -g root -m 0755 \
  "${TMPDIR}/${ASSET}" \
  /usr/local/lib/docker/cli-plugins/docker-compose

docker compose version
