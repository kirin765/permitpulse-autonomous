from __future__ import annotations

from django.conf import settings

from permitpulse.models import AutonomyEvent
from permitpulse.services.ingestion import ingest_city_rules
from permitpulse.services.runbook import record_slo_metrics, run_autonomous_recovery_cycle


def ingest_rules_for_city(city_code: str) -> dict:
    snapshot = ingest_city_rules(city_code)
    return {
        "city_code": city_code,
        "snapshot_id": getattr(snapshot, "id", None),
        "status": getattr(snapshot, "status", "missing"),
    }


def ingest_all_cities() -> dict:
    results = []
    for city_code in settings.PERMITPULSE_CITY_CODES:
        results.append(ingest_rules_for_city(city_code))
    AutonomyEvent.objects.create(
        event_type="data_loop",
        trigger="schedule:daily_city_ingestion",
        action_taken="ingest_all_cities",
        outcome="healthy",
        details={"results": results},
    )
    return {"results": results}


def evaluate_slos() -> dict:
    metrics = record_slo_metrics()
    return {
        "metrics": [
            {
                "metric_name": metric.metric_name,
                "value": metric.metric_value,
                "status": metric.status,
            }
            for metric in metrics
        ]
    }


def run_autonomous_recovery() -> dict:
    return run_autonomous_recovery_cycle()
