#!/usr/bin/env python3
"""Guarded, idempotent, EC2-only production runtime setup.

No Terraform changes, migrations, instance replacement or application startup.
Inputs/SSM commands contain identifiers only; database secrets stay on EC2.
"""
from __future__ import annotations

import argparse
import importlib
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse

ROOT = Path('/opt/opsflow')
SHARED = ROOT / 'shared'
RELEASES = ROOT / 'releases'
CERT_URL = 'https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem'
AUTH_NAMES = (
    'JWT_SECRET_KEY', 'JWT_REFRESH_SECRET_KEY', 'JWT_REAUTH_SECRET_KEY',
    'CSRF_SECRET_KEY', 'AUTH_THROTTLE_SECRET_KEY', 'SECURITY_EVENT_HMAC_KEY',
)
SERVICE_FILES = (
    'core-service-identity-private.pem', 'core-service-identity-public.pem',
    'incident-service-identity-private.pem', 'incident-service-identity-public.pem',
)

class Stop(RuntimeError):
    """Expected guarded failure: do not include credentials in messages."""


def assert_linux_root() -> None:
    effective_uid = getattr(os, 'geteuid', None)
    if sys.platform != 'linux' or not callable(effective_uid) or effective_uid() != 0:
        raise Stop('Run through EC2 AWS-RunShellScript as root; not on Windows')


def validate_inputs(data: dict[str, object], mode: str) -> dict[str, str]:
    required = (
        'release_tag', 'aws_region', 'rds_host', 'core_secret_arn',
        'incident_secret_arn', 'task_queue_url', 'realtime_notification_queue_url',
        'task_execution_table_name', 'task_execution_status_index_name',
    )
    for field in required:
        val = data.get(field)
        if not isinstance(val, str) or not val.strip() or 'YOUR_' in val or val == 'None':
            raise Stop(f'Missing non-secret runtime input: {field}')
    result = {name: str(data[name]).strip() for name in required}
    if re.fullmatch(r'[a-f0-9]{12}', result['release_tag']) is None:
        raise Stop('Release tag must be the ORIGINAL 12-character release prefix')
    if re.fullmatch(r'[a-z]{2}(?:-gov)?-[a-z]+(?:-[a-z]+)?-[0-9]', result['aws_region']) is None:
        raise Stop('Invalid AWS Region identifier')
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{4,254}', result['rds_host']) is None:
        raise Stop('Invalid RDS hostname')
    for name in ('core_secret_arn', 'incident_secret_arn'):
        if not result[name].startswith(f'arn:aws:secretsmanager:{result["aws_region"]}:'):
            raise Stop(f'{name} must match deployment Region')
    if mode == 'configure':
        for name in ('frontend_origin', 'ses_from_email'):
            value = data.get(name)
            if (not isinstance(value, str) or not value.strip() or
                    'YOUR-OWN-DOMAIN' in value.upper() or 'REPLACE_' in value.upper()
                    or 'YOUR_' in value.upper()):
                raise Stop(f'{name} must be supplied before production configuration')
            result[name] = value.strip()
        u = urlparse(result['frontend_origin'])
        if (u.scheme != 'https' or not u.netloc or u.username is not None or
                u.password is not None or u.path not in ('', '/') or u.query or u.fragment or
                not u.hostname or '.' not in u.hostname or u.port not in (None, 443) or
                u.hostname in ('localhost', 'example.com', 'example.invalid') or
                u.hostname.endswith(('.invalid', '.localhost', '.test', '.example'))):
            raise Stop('Provide the real HTTPS origin only, e.g. https://app.yourdomain.com')
        if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result['ses_from_email']) is None:
            raise Stop('Provide your verified SES sender email address')
    return result


def run_safe(argv: list[str], *, env: dict[str, str] | None = None,
             timeout: int = 40) -> str:
    proc = subprocess.run(argv, env=env, capture_output=True, text=True,
                          check=False, timeout=timeout)
    if proc.returncode:
        # Only classify fixed, non-secret error strings. Never print raw stderr:
        # a driver diagnostic can include a connection URL or username.
        if argv[:2] == ['docker', 'run']:
            message = proc.stderr.lower()
            if 'restored alembic revisions' in message:
                raise Stop('Database Alembic revision differs from release; do not migrate automatically')
            if 'certificate verify failed' in message or 'ssl error' in message:
                raise Stop('RDS TLS certificate or hostname verification failed')
            if 'password authentication failed' in message:
                raise Stop('Restricted RDS runtime authentication failed; do not rotate automatically')
            raise Stop('Read-only database probe failed; inspect endpoint, network and RDS roles (stderr suppressed)')
        raise Stop(f'Command failed without displaying potentially sensitive output: {argv[0]}')
    return proc.stdout.strip()


def get_secret(region: str, arn: str, host: str, name: str, db: str) -> dict[str, str]:
    raw = run_safe(['aws', 'secretsmanager', 'get-secret-value', '--region', region,
                    '--secret-id', arn, '--version-stage', 'AWSCURRENT',
                    '--query', 'SecretString', '--output', 'text'])
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Stop(f'Invalid JSON in {name} database secret') from exc
    required = {'engine': 'postgres', 'host': host, 'port': 5432,
                'dbname': db, 'username': name}
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in required.items()):
        raise Stop(f'Secret metadata does not match {db}; STOP (no rotation)')
    if not isinstance(value.get('password'), str) or len(value['password']) < 32:
        raise Stop(f'Secret password absent or too short for {db}; STOP')
    return value


def database_url(secret: dict[str, str], cert_path: str = '/run/secrets/rds_ca_bundle') -> str:
    # Render with URL-encoded credentials; never display it in output or CLI args.
    user = quote(secret['username'], safe='')
    password = quote(secret['password'], safe='')
    parameters = urlencode({'sslmode': 'verify-full', 'sslrootcert': cert_path})
    return (f'postgresql+psycopg://{user}:{password}@{secret["host"]}:5432/'
            f'{secret["dbname"]}?{parameters}')


def private_directory(p: Path) -> None:
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(p, 0o700)


def create_once(path: Path, content: bytes, permissions: int) -> None:
    """No replacement or truncation: existing configuration is authoritative."""
    if path.is_symlink():
        raise Stop(f'Unexpected symlink at {path.name}')
    if path.exists():
        if not path.is_file() or path.read_bytes() != content:
            raise Stop(f'Existing {path.name} differs; manually reconcile, never rotate automatically')
        if path.stat().st_mode & 0o777 != permissions:
            raise Stop(f'Existing {path.name} has unexpected permissions')
        return
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, permissions)
    try:
        fchmod = getattr(os, 'fchmod', None)
        if not callable(fchmod):
            raise Stop('Required Linux fchmod is unavailable')
        fchmod(fd, permissions)
        with os.fdopen(fd, 'wb') as dest:
            fd = -1
            dest.write(content)
            dest.flush()
            os.fsync(dest.fileno())
    except Exception:
        if fd >= 0:
            os.close(fd)
        path.unlink(missing_ok=True)
        raise


def release_dir(tag: str) -> Path:
    root = RELEASES / tag
    marker = root / '.receive_verified'
    if not marker.is_file() or marker.read_text(encoding='utf-8').strip() != tag:
        raise Stop('Verified release is not installed. Complete release recovery FIRST')
    manifest = root / 'release.json'
    if not manifest.is_file():
        raise Stop('Verified release manifest missing')
    try:
        meta = json.loads(manifest.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise Stop('Invalid release manifest') from exc
    if (meta.get('tag') != tag or not str(meta.get('commit', '')).startswith(tag)
            or meta.get('platform') != 'linux/amd64'):
        raise Stop('Release marker and manifest mismatch')
    files = meta.get('files')
    checksums = root / 'SHA256SUMS'
    if not isinstance(files, dict) or not checksums.is_file():
        raise Stop('Release file manifest or checksums absent')
    checksum_rows = {}
    for row in checksums.read_text(encoding='ascii').splitlines():
        pair = row.split('  ', 1)
        if len(pair) != 2 or re.fullmatch(r'[a-f0-9]{64}', pair[0]) is None:
            raise Stop('Unexpected release checksum format')
        if pair[1] in checksum_rows:
            raise Stop('Duplicate release checksum entry')
        checksum_rows[pair[1]] = pair[0]
    for name in (f'opsflow-source-{tag}.zip', 'receive_release.sh'):
        path = root / name
        meta_file = files.get(name)
        if not path.is_file() or not isinstance(meta_file, dict):
            raise Stop(f'Release artifact missing: {name}')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if (digest != meta_file.get('sha256') or len(content) != meta_file.get('bytes')
                or checksum_rows.get(name) != digest):
            raise Stop(f'Release artifact verification failed: {name}')
    if not (root / 'app' / 'compose.production.yaml').is_file():
        raise Stop('Production Compose file missing from release')
    for component in ('opsflow-backend', 'opsflow-incident-service', 'opsflow-frontend'):
        arch = run_safe(['docker', 'image', 'inspect', '--format',
                         '{{.Os}}/{{.Architecture}}', f'{component}:{tag}'])
        if arch != 'linux/amd64':
            raise Stop(f'Missing verified Linux/amd64 image: {component}')
    return root


def certificate() -> Path:
    folder = SHARED / 'certs'
    private_directory(folder)
    dest = folder / 'global-bundle.pem'
    if dest.exists():
        if dest.is_symlink():
            raise Stop('Unexpected certificate symlink')
        content = dest.read_bytes()
    else:
        # Standard trust-store TLS verifies the certificate-download endpoint.
        with urllib.request.urlopen(CERT_URL, context=ssl.create_default_context(), timeout=30) as stream:
            content = stream.read(262_144 + 1)
        if len(content) > 262_144:
            raise Stop('RDS CA bundle exceeds size limit')
    if b'-----BEGIN CERTIFICATE-----' not in content or b'-----END CERTIFICATE-----' not in content:
        raise Stop('Downloaded RDS trust bundle did not contain PEM certificates')
    create_once(dest, content, 0o444)
    return dest


def ensure_keypair(name: str) -> None:
    folder = SHARED / 'secrets'
    private_directory(folder)
    private = folder / f'{name}-private.pem'
    public = folder / f'{name}-public.pem'
    if private.exists() != public.exists() or private.is_symlink() or public.is_symlink():
        raise Stop(f'Incomplete or symlinked {name} keypair; do not regenerate')
    if not private.exists():
        with tempfile.TemporaryDirectory(prefix='.keys-', dir=folder) as tmp:
            temp_private = Path(tmp) / 'private.pem'
            temp_public = Path(tmp) / 'public.pem'
            run_safe(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt',
                      'rsa_keygen_bits:3072', '-out', str(temp_private)], timeout=120)
            os.chmod(temp_private, 0o600)
            pub = run_safe(['openssl', 'pkey', '-in', str(temp_private), '-pubout']) + '\n'
            temp_public.write_text(pub, encoding='ascii')
            os.chmod(temp_public, 0o444)
            # Move only after generating both; an interrupted move triggers a safety stop.
            os.replace(temp_private, private)
            os.replace(temp_public, public)
    match = run_safe(['openssl', 'pkey', '-in', str(private), '-pubout']).strip()
    if match != public.read_text(encoding='ascii').strip():
        raise Stop(f'Stored {name} public/private keys do not match')
    if private.stat().st_mode & 0o777 != 0o600 or public.stat().st_mode & 0o777 != 0o444:
        raise Stop(f'Unexpected {name} key permissions')


def auth_keys() -> dict[str, str]:
    folder = SHARED / 'secrets'
    private_directory(folder)
    path = folder / 'auth-keys.json'
    if path.exists():
        if path.is_symlink() or path.stat().st_mode & 0o777 != 0o600:
            raise Stop('Existing auth material is symlinked or incorrectly permissioned')
        try:
            existing = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise Stop('Existing auth material is invalid; STOP') from exc
        if (not isinstance(existing, dict) or set(existing) != set(AUTH_NAMES)
                or any(not isinstance(existing[k], str) or len(existing[k]) < 40 for k in AUTH_NAMES)
                or len(set(existing.values())) != len(AUTH_NAMES)):
            raise Stop('Existing auth keys are incomplete or weak; STOP')
        return existing
    generated = {key: secrets.token_urlsafe(48) for key in AUTH_NAMES}
    create_once(path, (json.dumps(generated, separators=(',', ':')) + '\n').encode(), 0o600)
    return generated


def render_env(mapping: dict[str, str]) -> bytes:
    """Tightly controlled env-file fields; no expansion or shell parsing."""
    for key, val in mapping.items():
        if re.fullmatch(r'[A-Z][A-Z0-9_]*', key) is None:
            raise Stop('Invalid environment key')
        if not isinstance(val, str) or any(c in val for c in '\r\n\x00$`'):
            raise Stop(f'Unsafe environment value: {key}')
    return ('\n'.join(f'{k}={v}' for k, v in mapping.items()) + '\n').encode('utf-8')


def verify_databases(tag: str, secrets_by_db: dict[str, dict[str, str]], cert: Path) -> None:
    """Real TLS/SQL and Alembic head checks, never apply migrations."""
    dbs = {'opsflow': 'opsflow-backend', 'opsflow_incidents': 'opsflow-incident-service'}
    probe = '''import os\nfrom alembic.config import Config\nfrom alembic.script import ScriptDirectory\nfrom sqlalchemy.engine import make_url\nimport psycopg\nu=make_url(os.environ['DATABASE_URL'])\nassert u.query.get('sslmode') == 'verify-full'\nassert u.query.get('sslrootcert') == '/run/secrets/rds_ca_bundle'\nwith psycopg.connect(host=u.host,port=u.port,dbname=u.database,user=u.username,password=u.password,sslmode='verify-full',sslrootcert='/run/secrets/rds_ca_bundle',options='-c default_transaction_read_only=on',connect_timeout=8) as c:\n    row=c.execute('select current_database(),current_user,(select ssl from pg_stat_ssl where pid=pg_backend_pid())').fetchone()\n    if row != (os.environ['EXPECTED_DB'],os.environ['EXPECTED_USER'],True): raise RuntimeError('Unexpected DB identity or missing TLS')\n    actual={r[0] for r in c.execute('select version_num from alembic_version')}\nheads=set(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())\nif not heads or actual != heads: raise RuntimeError('Restored Alembic revisions do not match this release')\nprint('PASS: verified-full TLS, restricted login and exact Alembic heads for '+os.environ['EXPECTED_DB'])\n'''
    for db, image in dbs.items():
        info = secrets_by_db[db]
        with tempfile.TemporaryDirectory(prefix='.dbcheck-', dir=SHARED) as tmp:
            envpath = Path(tmp) / 'runtime.env'
            envpath.write_bytes(render_env({'DATABASE_URL': database_url(info),
                                            'EXPECTED_DB': db,
                                            'EXPECTED_USER': info['username']}))
            os.chmod(envpath, 0o600)
            # Secrets never appear in the process argument list or SSM output.
            run_safe(['docker', 'run', '--rm', '--network', 'bridge',
                      '--read-only', '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
                      '--env-file', str(envpath), '--mount',
                      f'type=bind,src={cert},dst=/run/secrets/rds_ca_bundle,readonly',
                      '--entrypoint', 'python', f'{image}:{tag}', '-c', probe], timeout=100)
        print(f'PASS: RDS certificate-verified connection and migration heads: {db}')


def stage(tag: str, core: dict[str, str], incident: dict[str, str]) -> None:
    certificate()
    ensure_keypair('core-service-identity')
    ensure_keypair('incident-service-identity')
    auth_keys()
    verify_databases(tag, {'opsflow': core, 'opsflow_incidents': incident}, certificate())
    create_once(SHARED / 'runtime-staged', f'{tag}\n'.encode(), 0o600)
    print('PASS: Persistent signing keys, service identities and verified RDS connections staged')


def configure(data: dict[str, str], root: Path,
              core: dict[str, str], incident: dict[str, str],
              *, preview: bool = False) -> None:
    tag = data['release_tag']
    staged = SHARED / 'runtime-staged'
    if not staged.is_file() or staged.read_text(encoding='utf-8').strip() != tag:
        raise Stop('Run --mode stage for this exact release and verify both databases first')
    app = root / 'app'
    runtime = app / '.opsflow-runtime'
    private_directory(runtime)
    for folder in ('secrets', 'certs'):
        private_directory(runtime / folder)
    for filename in SERVICE_FILES:
        create_once(runtime / 'secrets' / filename,
                    (SHARED / 'secrets' / filename).read_bytes(), 0o444)
    create_once(runtime / 'certs' / 'global-bundle.pem', certificate().read_bytes(), 0o444)
    auth = auth_keys()
    backend = dict({'DATABASE_URL': database_url(core)}, **auth)
    create_once(runtime / 'backend.env', render_env(backend), 0o600)
    create_once(runtime / 'incident.env', render_env({'DATABASE_URL': database_url(incident)}), 0o600)
    # A loopback-only preview MUST NOT create production config or claim SES is ready.
    # Never use this environment for real users or expose it through an ALB.
    effective_origin = ('http://127.0.0.1:8080' if preview
                        else data['frontend_origin'])
    effective_sender = ('disabled@example.invalid' if preview
                        else data['ses_from_email'])
    compose_environment = {
        'OPSFLOW_IMAGE_TAG': tag,
        'AWS_REGION': data['aws_region'],
        'FRONTEND_ORIGIN': effective_origin,
        'PASSWORD_RESET_URL': effective_origin.rstrip('/') + '/reset-password',
        'SES_FROM_EMAIL': effective_sender,
        'TASK_QUEUE_URL': data['task_queue_url'],
        'REALTIME_NOTIFICATION_QUEUE_URL': data['realtime_notification_queue_url'],
        'TASK_EXECUTION_TABLE_NAME': data['task_execution_table_name'],
        'TASK_EXECUTION_STATUS_INDEX_NAME': data['task_execution_status_index_name'],
        'OPSFLOW_LOCAL_HTTP_PORT': '8080',
    }
    env_filename = '.env.preview' if preview else '.env.production'
    create_once(app / env_filename, render_env(compose_environment), 0o600)
    override = Path(__file__).with_name('compose.runtime.yaml')
    if not override.is_file():
        raise Stop('Runtime Compose override file missing')
    create_once(app / 'compose.runtime.yaml', override.read_bytes(), 0o600)
    # Compose config can be run with --quiet so no injected values are logged.
    # subprocess working-directory explicitly set rather than relying on SSM CWD.
    check = subprocess.run(['docker', 'compose', '--env-file', env_filename,
                            '-f', 'compose.production.yaml', '-f', 'compose.runtime.yaml',
                            'config', '--quiet'], cwd=app, capture_output=True, text=True,
                           check=False, timeout=40)
    if check.returncode:
        raise Stop('Production Compose merge validation failed; output suppressed to protect secrets')
    marker_name = 'runtime-preview-configured' if preview else 'runtime-configured'
    create_once(runtime / marker_name, f'{tag}\n'.encode(), 0o600)
    if preview:
        print('PASS: Loopback preview Compose validated; SES and public HTTPS NOT configured')
        print('PREVIEW ONLY: no email tests, no public traffic, no ALB exposure')
    else:
        print('PASS: Production runtime files prepared and Docker Compose configuration validated')
    print('No application containers started; no database migrations executed')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('inspect', 'stage', 'preview', 'configure'), required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    args = parser.parse_args()
    assert_linux_root()
    data = validate_inputs(json.loads(args.inputs.read_text(encoding='utf-8')), args.mode)
    for executable in ('aws', 'docker'):
        if shutil.which(executable) is None:
            raise Stop(f'Missing runtime requirement: {executable}')
    root = release_dir(data['release_tag'])
    if args.mode == 'inspect':
        print('PASS: Original release and all three Linux/amd64 images installed')
        return 0
    with socket.create_connection((data['rds_host'], 5432), timeout=6):
        pass
    core = get_secret(data['aws_region'], data['core_secret_arn'], data['rds_host'],
                      'opsflow_core_login', 'opsflow')
    incident = get_secret(data['aws_region'], data['incident_secret_arn'], data['rds_host'],
                          'opsflow_incidents_login', 'opsflow_incidents')
    print('PASS: RDS TCP connectivity and two restricted Secrets Manager credentials verified')
    private_directory(SHARED)
    with (SHARED / '.runtime-setup.lock').open('a+') as lock:
        fcntl = importlib.import_module('fcntl')  # Linux only, after assert_linux_root
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.mode == 'stage':
            if shutil.which('openssl') is None:
                raise Stop('Install openssl on EC2 before staging service identities')
            stage(data['release_tag'], core, incident)
        else:
            configure(data, root, core, incident, preview=(args.mode == 'preview'))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Stop, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'STOP: {exc}', file=sys.stderr)
        raise SystemExit(1) from None
