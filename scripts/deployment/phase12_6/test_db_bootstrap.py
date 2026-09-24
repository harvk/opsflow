from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_db_roles import pgpass_field, sql_string  # noqa: E402
from prepare_db_bootstrap_ssm import build_payload  # noqa: E402


class BootstrapPureTests(unittest.TestCase):
    def test_pgpass_escapes_colons_and_slashes(self):
        self.assertEqual(pgpass_field("a:b\\c"), "a\\:b\\\\c")

    def test_sql_quotes_embedded_apostrophes(self):
        self.assertEqual(sql_string("a'b"), "'a''b'")

    def test_sql_rejects_nul(self):
        with self.assertRaises(ValueError):
            sql_string("a\x00b")

    def test_ssm_payload_never_contains_generated_credentials(self):
        source = b"print('this is deployment script source')"
        payload = build_payload({"AWS_REGION": "us-east-1", "RDS_HOST": "db.example"}, source)
        self.assertTrue(payload["commands"][0].startswith("set"))
        self.assertTrue(any("base64 --decode" in c for c in payload["commands"]))
        self.assertTrue(any("AWS_REGION=" in c for c in payload["commands"]))
        self.assertNotIn("password", str(payload).lower())


if __name__ == "__main__":
    unittest.main()
