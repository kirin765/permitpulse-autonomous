from __future__ import annotations

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from permitpulse.models import (
    AutonomyEvent,
    CustomerPolicyAction,
    Organization,
    RollbackEvent,
    RuleClause,
    RuleSnapshot,
)
from permitpulse.services.ingestion import ingest_city_rules
from permitpulse.services.runbook import run_autonomous_recovery_cycle


class PermitPulseAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.org = Organization.objects.create(name="Acme Hosts", slug="acme", plan="starter")

    def _create_snapshot(self, city_code: str = "NYC", score: float = 0.9, status: str = "ACTIVE") -> RuleSnapshot:
        snapshot = RuleSnapshot.objects.create(
            city_code=city_code,
            version=1,
            checksum="checksum-1",
            status=status,
            validation_score=score,
            source_urls=["https://example.com/rule"],
            parsed_payload={"parser_traces": ["test"]},
            is_active=True,
        )
        RuleClause.objects.create(
            snapshot=snapshot,
            clause_id="registration-required",
            category="requirement",
            condition_expr={},
            requirement_text="Register before operating.",
            penalty_text="Penalty up to $500/day.",
            confidence=0.9,
        )
        return snapshot

    def test_create_address_check_and_provenance(self):
        self._create_snapshot()
        response = self.client.post(
            "/api/v1/address-checks",
            data={"address": "123 Main St, New York, NY", "city_code": "NYC", "context": {}},
            format="json",
            HTTP_X_ORG_SLUG="acme",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["city_code"], "NYC")
        self.assertIn("provenance", response.data)
        self.assertIn("checksum", response.data["provenance"])

    def test_low_confidence_forces_auto_conservative(self):
        self._create_snapshot(score=0.3)
        response = self.client.post(
            "/api/v1/address-checks",
            data={"address": "789 Low Confidence Rd", "city_code": "NYC", "context": {}},
            format="json",
            HTTP_X_ORG_SLUG="acme",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["decision_mode"], "AUTO_CONSERVATIVE")

    def test_portfolio_import(self):
        self._create_snapshot()
        csv_content = "address,city_code,is_primary_residence\n123 Main St,NYC,true\n"
        response = self.client.post(
            "/api/v1/portfolio/import",
            data={"file": self._as_uploaded(csv_content, "portfolio.csv")},
            HTTP_X_ORG_SLUG="acme",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["row_count"], 1)

    def test_billing_webhook_creates_policy_action(self):
        payload = {
            "id": "evt_1",
            "type": "invoice.payment_failed",
            "data": {"object": {"metadata": {"org_slug": "acme"}}},
        }
        response = self.client.post(
            "/api/v1/billing/webhook",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CustomerPolicyAction.objects.filter(action_type="payment_failed").exists())

    def test_autonomy_status_endpoint(self):
        self._create_snapshot()
        AutonomyEvent.objects.create(
            event_type="ops_loop",
            trigger="test",
            action_taken="noop",
            outcome="healthy",
            details={},
        )
        response = self.client.get("/api/v1/system/autonomy-status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("city_snapshots", response.data)

    def test_supabase_status_endpoint_not_configured(self):
        response = self.client.get("/api/v1/system/supabase-status")
        self.assertEqual(response.status_code, 200)
        self.assertIn(response.data["status"], {"not_configured", "degraded", "connected"})
        self.assertIn("db", response.data)
        self.assertIn("rest", response.data)

    @patch("permitpulse.views.supabase_status_payload")
    def test_supabase_status_endpoint_mocked_connected(self, supabase_status_payload_mock):
        supabase_status_payload_mock.return_value = {
            "status": "connected",
            "db": {"configured": True, "connected": True, "host": "example.supabase.co", "error": ""},
            "rest": {"configured": True, "reachable": True, "status_code": 200, "latency_ms": 123, "error": ""},
        }
        response = self.client.get("/api/v1/system/supabase-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "connected")

    @override_settings(CRON_SHARED_SECRET="test-cron-secret")
    @patch("permitpulse.views.run_daily_maintenance")
    def test_daily_maintenance_requires_auth(self, run_daily_maintenance_mock):
        response = self.client.post("/api/v1/internal/cron/daily-maintenance", format="json")
        self.assertEqual(response.status_code, 401)
        run_daily_maintenance_mock.assert_not_called()

    @override_settings(CRON_SHARED_SECRET="test-cron-secret")
    @patch("permitpulse.views.run_daily_maintenance")
    def test_daily_maintenance_with_bearer_token(self, run_daily_maintenance_mock):
        run_daily_maintenance_mock.return_value = {
            "started_at": "2026-02-27T00:00:00Z",
            "finished_at": "2026-02-27T00:01:00Z",
            "cities_processed": [],
            "snapshots_published": 0,
            "slo_metrics_count": 2,
            "recovery_actions": 0,
            "status": "healthy",
        }
        response = self.client.post(
            "/api/v1/internal/cron/daily-maintenance",
            format="json",
            HTTP_AUTHORIZATION="Bearer test-cron-secret",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("started_at", response.data)
        self.assertEqual(response.data["status"], "healthy")
        run_daily_maintenance_mock.assert_called_once()

    @patch("permitpulse.views.run_daily_maintenance")
    def test_daily_maintenance_allows_vercel_cron_header(self, run_daily_maintenance_mock):
        run_daily_maintenance_mock.return_value = {
            "started_at": "2026-02-27T00:00:00Z",
            "finished_at": "2026-02-27T00:01:00Z",
            "cities_processed": [],
            "snapshots_published": 0,
            "slo_metrics_count": 2,
            "recovery_actions": 0,
            "status": "healthy",
        }
        response = self.client.get(
            "/api/v1/internal/cron/daily-maintenance",
            HTTP_X_VERCEL_CRON="0 3 * * *",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")

    @patch("permitpulse.services.ingestion.fetch_city_document")
    def test_ingestion_failure_keeps_previous_snapshot(self, fetch_city_document_mock):
        previous = self._create_snapshot()
        fetch_city_document_mock.side_effect = RuntimeError("network down")

        snapshot = ingest_city_rules("NYC")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.id, previous.id)
        previous.refresh_from_db()
        self.assertEqual(previous.status, "STALE")

    def test_runbook_auto_rollback(self):
        AutonomyEvent.objects.create(
            event_type="ops_loop",
            trigger="deploy:v2",
            action_taken="healthcheck_failed",
            outcome="degraded",
            details={"city_code": "NYC"},
            created_at=timezone.now(),
        )
        summary = run_autonomous_recovery_cycle()
        self.assertGreaterEqual(summary["actions_executed"], 1)
        self.assertTrue(RollbackEvent.objects.exists())

    @staticmethod
    def _as_uploaded(content: str, name: str):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")
