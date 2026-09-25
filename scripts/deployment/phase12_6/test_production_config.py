"""Offline regression tests for Phase 12.6C. No AWS calls."""
from __future__ import annotations

from pathlib import Path
import unittest

import yaml


class ProductionConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # In repository tests the file resides at scripts/deployment/phase12_6/.
        cls.repo = Path(__file__).resolve().parents[3]
        cls.text = (cls.repo / "compose.production.yaml").read_text(encoding="utf-8")
        cls.compose = yaml.safe_load(cls.text)

    def test_no_local_postgresql_or_test_database(self) -> None:
        services = self.compose["services"]
        self.assertFalse({"db", "migrate", "incident-migrate", "provision-databases"} & set(services))
        self.assertNotIn("TEST_DATABASE_URL", services["backend"].get("environment", {}))
        self.assertNotIn("TEST_DATABASE_URL", services["incident-service"].get("environment", {}))

    def test_not_public_before_alb(self) -> None:
        s = self.compose["services"]
        self.assertNotIn("ports", s["backend"])
        self.assertNotIn("ports", s["incident-service"])
        self.assertTrue(all(x.startswith("127.0.0.1:") for x in s["frontend"]["ports"]))

    def test_workers_require_explicit_profile(self) -> None:
        for name in ("incident-reconciler", "incident-outbox-relay", "incident-completion-outbox-relay"):
            self.assertEqual(self.compose["services"][name]["profiles"], ["workers"])

    def test_key_isolation(self) -> None:
        s = self.compose["services"]
        self.assertEqual(set(s["backend"]["secrets"]), {"core_service_identity_private_key", "incident_service_identity_public_key"})
        self.assertEqual(set(s["incident-service"]["secrets"]), {"core_service_identity_public_key", "incident_service_identity_private_key"})

    def test_frontend_proxy_contract(self) -> None:
        nginx = (self.repo / "frontend/nginx/production.conf").read_text(encoding="utf-8")
        self.assertIn("location /api/", nginx)
        self.assertIn("proxy_pass http://backend:8000;", nginx)
        self.assertEqual(self.compose["services"]["frontend"]["build"]["args"]["VITE_API_BASE_URL"], "/api/v1")

    def test_no_dev_credential_mounts(self) -> None:
        self.assertNotIn("AWS_HOST_CONFIG_DIR", self.text)
        self.assertNotIn("AWS_PROFILE", self.text)
        self.assertNotIn(".env.docker", self.text)


if __name__ == "__main__":
    unittest.main()
