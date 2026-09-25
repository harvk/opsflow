#!/usr/bin/env bash
# Phase 12.6D: EC2 receiver. Does NOT start containers or access DB secrets.
# Download this script + SHA256SUMS via SSM and compare its checksum FIRST.
# Execute: sudo env AWS_REGION=... RELEASE_BUCKET=... RELEASE_TAG=... bash /tmp/receive_release.sh
set -Eeuo pipefail
umask 077

: "${AWS_REGION:?Set AWS_REGION}"
: "${RELEASE_BUCKET:?Set RELEASE_BUCKET from Terraform}"
: "${RELEASE_TAG:?Set the exact 12-character commit SHA}"

if [[ $EUID -ne 0 ]]; then
  echo 'ERROR: Run this EC2 receiver with sudo as root.' >&2
  exit 1
fi
if [[ ! "$RELEASE_TAG" =~ ^[0-9a-f]{12}$ ]]; then
  echo 'ERROR: RELEASE_TAG must be the 12-character hexadecimal commit prefix.' >&2
  exit 1
fi
if [[ ! "$RELEASE_BUCKET" =~ ^[a-z0-9][a-z0-9.-]{2,62}$ ]]; then
  echo 'ERROR: Invalid release bucket name.' >&2
  exit 1
fi
[[ $(uname -m) == x86_64 ]] || { echo 'ERROR: Expected x86_64 EC2.' >&2; exit 1; }
for program in aws python3 gzip sha256sum docker df; do
  command -v "$program" >/dev/null || { echo "ERROR: Missing $program" >&2; exit 1; }
done

docker info >/dev/null
available_mb=$(df -Pm / | awk 'NR==2 {print $4}')
if [[ ! "$available_mb" =~ ^[0-9]+$ ]] || (( available_mb < 8192 )); then
  echo "ERROR: Only ${available_mb:-unknown} MiB free on /; 8 GiB required before loading images." >&2
  exit 1
fi

root=/opt/opsflow/releases
final="$root/$RELEASE_TAG"
if [[ -e "$final" ]]; then
  echo "ERROR: $final already exists. Verify existing release; do not overwrite." >&2
  exit 1
fi
install -d -o root -g root -m 0750 "$root"
stage=$(mktemp -d "$root/.incoming-${RELEASE_TAG}-XXXXXXXX")
chmod 0700 "$stage"
prefix="s3://${RELEASE_BUCKET}/releases/${RELEASE_TAG}/"
# The source and image archive are downloaded directly to the protected staging area.
for name in "opsflow-source-${RELEASE_TAG}.zip" "opsflow-images-${RELEASE_TAG}.tar.gz" \
            receive_release.sh SHA256SUMS release.json; do
  aws s3 cp "${prefix}${name}" "$stage/$name" --region "$AWS_REGION" --only-show-errors
done

(
  cd "$stage"
  sha256sum -c SHA256SUMS
)
# Check the untrusted metadata and zip member paths before extraction.
python3 - "$stage" "$RELEASE_TAG" <<'PY'
import json
import pathlib
import sys
import zipfile

root = pathlib.Path(sys.argv[1])
tag = sys.argv[2]
meta = json.loads((root / 'release.json').read_text())
if meta.get('tag') != tag or meta.get('platform') != 'linux/amd64' or not meta.get('commit', '').startswith(tag):
    raise SystemExit('ERROR: Invalid release manifest metadata')
zip_path = root / f'opsflow-source-{tag}.zip'
with zipfile.ZipFile(zip_path) as z:
    if z.testzip() is not None:
        raise SystemExit('ERROR: Source ZIP checksum failed')
    for member in z.namelist():
        p = pathlib.PurePosixPath(member)
        if p.is_absolute() or '..' in p.parts or '\\' in member or ':' in member:
            raise SystemExit(f'ERROR: Unsafe ZIP member {member!r}')
    z.extractall(root / 'app')
if not (root / 'app' / 'compose.production.yaml').is_file():
    raise SystemExit('ERROR: Production Compose configuration missing')
PY

echo 'Checksums and source structure verified; loading Docker images...'
gzip -dc "$stage/opsflow-images-${RELEASE_TAG}.tar.gz" | docker load
for image in opsflow-backend opsflow-incident-service opsflow-frontend; do
  expected="${image}:${RELEASE_TAG}"
  architecture=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$expected")
  if [[ "$architecture" != 'linux/amd64' ]]; then
    echo "ERROR: Image $expected has unexpected architecture $architecture" >&2
    exit 1
  fi
  echo "PASS: $expected ($architecture)"
done

# Images are installed into Docker's storage: keeping the uploaded tar.gz on
# this 30-GiB host would waste disk. Retain source zip, checksum, manifest.
rm -f "$stage/opsflow-images-${RELEASE_TAG}.tar.gz"
printf '%s\n' "$RELEASE_TAG" > "$stage/.receive_verified"
chmod -R go-rwx "$stage"
mv -- "$stage" "$final"
echo "PASS: Verified release installed at $final"
echo 'No containers have been started and no production secrets transferred.'
