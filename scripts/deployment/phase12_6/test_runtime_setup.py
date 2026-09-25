"""Cross-platform pure/unit validation; no Bash, AWS, Docker or temp directories."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

import prepare_runtime_ssm as builder
import stage_production_runtime as runtime

DATA = {
    'release_tag': '29b5857b88c0', 'aws_region': 'us-east-1',
    'rds_host': 'opsflow-db.abcdefghijkl.us-east-1.rds.amazonaws.com',
    'core_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:core-123',
    'incident_secret_arn': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:incident-123',
    'task_queue_url': 'https://sqs.us-east-1.amazonaws.com/123456789012/task',
    'realtime_notification_queue_url': 'https://sqs.us-east-1.amazonaws.com/123456789012/realtime',
    'task_execution_table_name': 'opsflow-tasks',
    'task_execution_status_index_name': 'status-gsi',
    'frontend_origin': '', 'ses_from_email': '',
}

class RuntimeTests(unittest.TestCase):
    def test_inspect_inputs_accept_without_public_origin(self) -> None:
        self.assertEqual(runtime.validate_inputs(DATA, 'inspect')['release_tag'], DATA['release_tag'])
        runtime.validate_inputs(DATA, 'stage')


    def test_preview_works_without_domain_or_ses(self) -> None:
        self.assertEqual(runtime.validate_inputs(DATA, 'preview')['release_tag'], DATA['release_tag'])
        # Production retains its strict prerequisite requirements.
        with self.assertRaises(runtime.Stop):
            runtime.validate_inputs(DATA, 'configure')

    def test_preview_ssm_is_separate_from_production_configuration(self) -> None:
        params = builder.build_params('preview', DATA, b'print("sample")\n', b'services: {}\n')
        command = params['commands'][0]
        self.assertIn('--mode preview', command)
        self.assertNotIn('disabled@example.invalid', command)
        self.assertNotIn('password', command.lower())

    def test_preview_env_isolated_and_production_env_unchanged(self) -> None:
        from pathlib import Path
        # No Linux subprocess, no AWS and no Bash. Pure Python probe of mode names.
        self.assertIn("env_filename = '.env.preview' if preview else '.env.production'",
                      Path(runtime.__file__).read_text(encoding='utf-8'))
        self.assertIn("'runtime-preview-configured' if preview else 'runtime-configured'",
                      Path(runtime.__file__).read_text(encoding='utf-8'))

    def test_missing_terraform_output_is_rejected(self) -> None:
        sample = dict(DATA)
        sample['rds_host'] = ''
        with self.assertRaises(runtime.Stop):
            runtime.validate_inputs(sample, 'stage')

    def test_real_public_origin_required_for_configuration(self) -> None:
        with self.assertRaises(runtime.Stop):
            runtime.validate_inputs(DATA, 'configure')
        sample = dict(DATA, frontend_origin='https://app.acme-corp.com',
                      ses_from_email='verified@acme-corp.com')
        self.assertEqual(runtime.validate_inputs(sample, 'configure')['frontend_origin'],
                         'https://app.acme-corp.com')

    def test_localhost_and_placeholder_origin_rejected(self) -> None:
        for origin in ('http://app.example.com', 'https://localhost', 'https://app.opsflow.test',
                       'https://example.invalid', 'https://app.acme-corp.com/reset'):
            with self.subTest(origin=origin), self.assertRaises(runtime.Stop):
                runtime.validate_inputs(dict(DATA, frontend_origin=origin,
                                              ses_from_email='verified@acme-corp.com'), 'configure')

    def test_sqlalchemy_url_percent_encodes_credentials_and_verifies_tls(self) -> None:
        url = runtime.database_url({'username': 'a+b', 'password': 'P:@/?$+% abc',
                                    'host': 'rds.example.com', 'dbname': 'opsflow'})
        self.assertIn('sslmode=verify-full', url)
        self.assertIn('sslrootcert=%2Frun%2Fsecrets%2Frds_ca_bundle', url)
        self.assertIn('a%2Bb:P%3A%40%2F%3F%24%2B%25%20abc@', url)

    def test_runtime_env_does_not_allow_newline_or_compose_interpolation(self) -> None:
        self.assertEqual(runtime.render_env({'APP_ENV': 'production'}), b'APP_ENV=production\n')
        for value in ('okay\nBAD=1', 'a${BAD}', 'x`whoami`'):
            with self.subTest(value=value), self.assertRaises(runtime.Stop):
                runtime.render_env({'BAD': value})

    def test_builder_reads_exact_terraform_outputs(self) -> None:
        outputs = {key: {'value': DATA[dest]} for dest, key in builder.OUTPUTS.items()}
        result = builder.collect_values(outputs,
                                        {'tag': DATA['release_tag'],
                                         'commit': DATA['release_tag'] + 'f' * 28})
        self.assertEqual(result['release_tag'], DATA['release_tag'])
        self.assertEqual(result['frontend_origin'], '')
        del outputs['task_queue_url']
        with self.assertRaises(ValueError):
            builder.collect_values(outputs, {'tag': DATA['release_tag'],
                                             'commit': DATA['release_tag'] + 'f' * 28})

    def test_ssm_commands_contain_no_password_or_bash_windows_calls(self) -> None:
        params = builder.build_params('stage', DATA, b'print("sample")\n', b'services: {}\n')
        self.assertEqual(list(params), ['commands'])
        command = params['commands'][0]
        self.assertIn('base64 -d', command)
        self.assertIn('stage_production_runtime.py --mode stage', command)
        self.assertNotIn('password', command.lower())

    def test_invalid_mode_rejected(self) -> None:
        with self.assertRaises(ValueError):
            builder.build_params('migrate', DATA, b'code', b'override')

    def test_validate_secret_metadata_without_exposing_value(self) -> None:
        with patch.object(runtime, 'run_safe', return_value=json.dumps({
            'engine': 'postgres', 'host': DATA['rds_host'], 'port': 5432,
            'dbname': 'opsflow', 'username': 'opsflow_core_login', 'password': 'S' * 44,
        })):
            secret = runtime.get_secret(DATA['aws_region'], DATA['core_secret_arn'],
                                        DATA['rds_host'], 'opsflow_core_login', 'opsflow')
            self.assertEqual(secret['username'], 'opsflow_core_login')
        with patch.object(runtime, 'run_safe', return_value=json.dumps({
            'engine': 'postgres', 'host': DATA['rds_host'], 'port': 5432,
            'dbname': 'wrong', 'username': 'opsflow_core_login', 'password': 'S' * 44,
        })):
            with self.assertRaises(runtime.Stop):
                runtime.get_secret(DATA['aws_region'], DATA['core_secret_arn'],
                                   DATA['rds_host'], 'opsflow_core_login', 'opsflow')

    def test_release_gate_refuses_missing_verified_marker(self) -> None:
        with patch.object(runtime, 'RELEASES', Path('/definitely/no/opsflow/releases')):
            with self.assertRaises(runtime.Stop):
                runtime.release_dir(DATA['release_tag'])

if __name__ == '__main__':
    unittest.main()
