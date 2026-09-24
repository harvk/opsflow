#!/usr/bin/env python3
"""Generate non-secret OpsFlow runtime inputs and safe SSM command parameters.

Run on Windows with backend/.venv/Scripts/python.exe. Never reads .env secrets,
passes DB passwords to SSM, or advances the original Git release tag.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import zlib
import json
import re
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parents[2]
TF_DIR = REPO / 'infrastructure' / 'terraform'
LOCAL = REPO / '.opsflow-migration' / 'phase12-6d'

OUTPUTS: dict[str, str] = {
    'aws_region': 'aws_region',
    'rds_host': 'live_rds_endpoint',
    'core_secret_arn': 'live_core_database_secret_arn',
    'incident_secret_arn': 'live_incident_database_secret_arn',
    'task_queue_url': 'task_queue_url',
    'realtime_notification_queue_url': 'realtime_notification_queue_url',
    'task_execution_table_name': 'incident_task_execution_table_name',
    'task_execution_status_index_name': 'incident_task_execution_status_index_name',
}


def collect_values(raw: dict[str, object], manifest: dict[str, object]) -> dict[str, str]:
    if (not isinstance(manifest.get('commit'), str) or
            not isinstance(manifest.get('tag'), str) or
            not manifest['commit'].startswith(manifest['tag']) or
            re.fullmatch(r'[a-f0-9]{12}', manifest['tag']) is None):
        raise ValueError('Invalid ORIGINAL release manifest; do not use git HEAD instead')
    values = {'release_tag': manifest['tag'], 'frontend_origin': '', 'ses_from_email': ''}
    for dest, name in OUTPUTS.items():
        item = raw.get(name)
        if not isinstance(item, dict) or not isinstance(item.get('value'), (str, int)):
            raise ValueError(f'Expected exact Terraform output missing: {name}')
        value = str(item['value']).strip()
        if not value or value in ('None', 'null'):
            raise ValueError(f'Empty Terraform output: {name}')
        values[dest] = value
    return values


def read_runtime_inputs(path: Path) -> dict[str, object]:
    values = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(values, dict):
        raise ValueError('Runtime inputs must be a JSON object')
    if any('password' in key.casefold() or 'private_key' in key.casefold() for key in values):
        raise ValueError('Do not put secret values in runtime inputs')
    return values


def build_params(mode: str, values: dict[str, object], script: bytes,
                 compose_override: bytes) -> dict[str, list[str]]:
    if mode not in ('inspect', 'stage', 'preview', 'configure'):
        raise ValueError('Unknown runtime operation')
    from stage_production_runtime import validate_inputs
    validate_inputs(values, mode)
    # Encoding is transport-only; content is non-secret and reviewed before SSM.
    path = '/tmp/opsflow-runtime-helper'
    commands = [
        'set -Eeuo pipefail',
        'umask 077',
        f'install -d -m 0700 {path}',
        (f"printf %s {base64.b64encode(zlib.compress(script, 9)).decode()} | base64 -d | "
         "python3 -c 'import zlib,sys;sys.stdout.buffer.write(zlib.decompress(sys.stdin.buffer.read()))' "
         f"> {path}/stage_production_runtime.py"),
        (f"echo '{hashlib.sha256(script).hexdigest()}  {path}/stage_production_runtime.py' "
         "| sha256sum --check --status"),
        f'printf %s {base64.b64encode(compose_override).decode()} | base64 -d > {path}/compose.runtime.yaml',
        (f'printf %s {base64.b64encode(json.dumps(values,separators=(",",":")).encode()).decode()} '
         f'| base64 -d > {path}/runtime-inputs.json'),
        f'python3 {path}/stage_production_runtime.py --mode {mode} --inputs {path}/runtime-inputs.json',
    ]
    return {'commands': ['\n'.join(commands)]}


def terraform_outputs() -> dict[str, object]:
    proc = subprocess.run(['terraform', 'output', '-json'], cwd=TF_DIR,
                          capture_output=True, text=True, check=False, timeout=40)
    if proc.returncode:
        raise RuntimeError('Unable to read Terraform outputs; restore AWS credentials and Terraform state')
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init', action='store_true', help='Create non-secret runtime-inputs.json from Terraform')
    parser.add_argument('--mode', choices=('inspect', 'stage', 'preview', 'configure'))
    args = parser.parse_args()
    if args.init == (args.mode is not None):
        parser.error('Select exactly one: --init OR --mode')
    LOCAL.mkdir(parents=True, exist_ok=True)
    inputs = LOCAL / 'runtime-inputs.json'
    if args.init:
        if inputs.exists():
            raise RuntimeError('Existing runtime-inputs.json: review rather than overwrite it')
        manifest = json.loads((LOCAL / 'release.json').read_text(encoding='utf-8'))
        values = collect_values(terraform_outputs(), manifest)
        inputs.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
        print(f'PASS: Non-secret inputs created: {inputs}')
        print('Inspect/stage now; add a real HTTPS origin and verified SES sender before configure')
        return 0
    if not inputs.is_file():
        raise RuntimeError('First run --init, using the original local release manifest')
    stage_script = (SCRIPT_DIR / 'stage_production_runtime.py').read_bytes()
    override = (REPO / 'compose.runtime.yaml').read_bytes()
    params = build_params(args.mode, read_runtime_inputs(inputs), stage_script, override)
    dest = LOCAL / f'runtime-{args.mode}-ssm-params.json'
    dest.write_text(json.dumps(params, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: Prepared {args.mode} command (no credentials): {dest}')
    print(f'SSM parameters payload: {dest.stat().st_size} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
