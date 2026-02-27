from __future__ import annotations

from permitpulse.models import SLOMetric


def latest_slo_summary() -> dict:
    metrics = list(SLOMetric.objects.order_by("metric_name", "-window_end")[:20])
    grouped: dict[str, SLOMetric] = {}
    for metric in metrics:
        if metric.metric_name not in grouped:
            grouped[metric.metric_name] = metric

    payload = {
        "metrics": [
            {
                "metric_name": metric.metric_name,
                "metric_value": metric.metric_value,
                "target_value": metric.target_value,
                "status": metric.status,
                "window_start": metric.window_start,
                "window_end": metric.window_end,
            }
            for metric in grouped.values()
        ]
    }
    return payload
