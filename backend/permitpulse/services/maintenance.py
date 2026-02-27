from __future__ import annotations

from datetime import datetime
from typing import Any

from django.conf import settings
from django.utils import timezone

from permitpulse.models import AutonomyEvent
from permitpulse.services.ingestion import ingest_city_rules
from permitpulse.services.runbook import record_slo_metrics, run_autonomous_recovery_cycle


def run_daily_maintenance() -> dict[str, Any]:
    started_at = timezone.now()
    city_results: list[dict[str, Any]] = []
    snapshots_published = 0

    for city_code in settings.PERMITPULSE_CITY_CODES:
        snapshot = ingest_city_rules(city_code)
        status = getattr(snapshot, "status", "missing")
        if snapshot and status == "ACTIVE":
            snapshots_published += 1
        city_results.append(
            {
                "city_code": city_code,
                "snapshot_id": getattr(snapshot, "id", None),
                "status": status,
            }
        )

    metrics = record_slo_metrics()
    recovery = run_autonomous_recovery_cycle()

    finished_at = timezone.now()
    status = "healthy"
    if any(item["status"] in {"FAILED", "STALE", "missing"} for item in city_results):
        status = "degraded"

    result: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "cities_processed": city_results,
        "snapshots_published": snapshots_published,
        "slo_metrics_count": len(metrics),
        "recovery_actions": int(recovery.get("actions_executed", 0)),
        "status": status,
    }

    AutonomyEvent.objects.create(
        event_type="ops_loop",
        trigger="api:daily_maintenance",
        action_taken="daily_maintenance_cycle",
        outcome=status,
        details=result,
    )
    return result
