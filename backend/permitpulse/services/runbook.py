from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from permitpulse.models import AutonomyEvent, RollbackEvent, RuleSnapshot, SLOMetric


def record_slo_metrics() -> list[SLOMetric]:
    now = timezone.now()
    window_start = now - timedelta(hours=24)

    total_checks = max(
        1,
        AutonomyEvent.objects.filter(
            event_type="decision_loop",
            created_at__gte=window_start,
        ).count(),
    )
    failed_checks = AutonomyEvent.objects.filter(
        event_type="decision_loop",
        outcome="degraded",
        created_at__gte=window_start,
    ).count()
    availability = round(((total_checks - failed_checks) / total_checks) * 100, 3)

    recoveries = AutonomyEvent.objects.filter(
        event_type="ops_loop",
        action_taken="auto_rollback",
        created_at__gte=window_start,
    ).count()
    incidents = AutonomyEvent.objects.filter(
        event_type="ops_loop",
        outcome="degraded",
        created_at__gte=window_start,
    ).count()
    auto_recovery_rate = round((recoveries / incidents) * 100, 3) if incidents else 100.0

    metrics = [
        SLOMetric.objects.create(
            metric_name="api_availability",
            metric_value=availability,
            target_value=settings.AUTONOMY_TARGET_AVAILABILITY,
            window_start=window_start,
            window_end=now,
            status="healthy" if availability >= settings.AUTONOMY_TARGET_AVAILABILITY else "breached",
        ),
        SLOMetric.objects.create(
            metric_name="auto_recovery_rate",
            metric_value=auto_recovery_rate,
            target_value=settings.AUTONOMY_TARGET_AUTO_RECOVERY,
            window_start=window_start,
            window_end=now,
            status="healthy" if auto_recovery_rate >= settings.AUTONOMY_TARGET_AUTO_RECOVERY else "breached",
        ),
    ]
    return metrics


def run_autonomous_recovery_cycle() -> dict:
    now = timezone.now()
    threshold = now - timedelta(minutes=10)

    degraded_events = AutonomyEvent.objects.filter(outcome="degraded", created_at__gte=threshold).order_by("-created_at")
    action_count = 0
    for event in degraded_events:
        trigger_key = f"event:{event.id}"
        already_handled = RollbackEvent.objects.filter(metadata__trigger_key=trigger_key).exists()
        if already_handled:
            continue

        fallback_snapshot = (
            RuleSnapshot.objects.filter(city_code=event.details.get("city_code", "NYC"), is_active=True)
            .order_by("-version")
            .first()
        )

        RollbackEvent.objects.create(
            failed_release=event.trigger,
            fallback_release=(f"snapshot:{fallback_snapshot.id}" if fallback_snapshot else "snapshot:none"),
            reason=f"Auto rollback due to degraded event {event.id}",
            metadata={"trigger_key": trigger_key, "event_type": event.event_type},
        )
        AutonomyEvent.objects.create(
            event_type="ops_loop",
            trigger=event.trigger,
            action_taken="auto_rollback",
            outcome="healthy",
            details={"trigger_event_id": event.id},
        )
        action_count += 1

    return {"actions_executed": action_count, "checked_events": degraded_events.count()}


def autonomy_status_payload() -> dict:
    snapshots = RuleSnapshot.objects.filter(is_active=True).order_by("city_code", "-version")
    city_map = {}
    stale_cities = []
    for snapshot in snapshots:
        city_map[snapshot.city_code] = {
            "version": snapshot.version,
            "status": snapshot.status,
            "validation_score": snapshot.validation_score,
            "published_at": snapshot.published_at,
        }
        if snapshot.status != "ACTIVE":
            stale_cities.append(snapshot.city_code)

    recent_events = list(
        AutonomyEvent.objects.order_by("-created_at")[:20].values(
            "id", "event_type", "trigger", "action_taken", "outcome", "created_at", "details"
        )
    )
    recent_rollbacks = list(
        RollbackEvent.objects.order_by("-created_at")[:10].values(
            "id", "failed_release", "fallback_release", "reason", "recovered_at"
        )
    )
    return {
        "city_snapshots": city_map,
        "recent_autonomy_events": recent_events,
        "recent_rollbacks": recent_rollbacks,
        "stale_cities": stale_cities,
    }
