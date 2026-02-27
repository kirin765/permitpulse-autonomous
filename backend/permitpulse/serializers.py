from __future__ import annotations

from rest_framework import serializers

from permitpulse import models


class RuleClauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RuleClause
        fields = (
            "clause_id",
            "category",
            "condition_expr",
            "requirement_text",
            "penalty_text",
            "confidence",
        )


class RuleSnapshotSerializer(serializers.ModelSerializer):
    clauses = RuleClauseSerializer(many=True, read_only=True)

    class Meta:
        model = models.RuleSnapshot
        fields = (
            "id",
            "city_code",
            "version",
            "checksum",
            "effective_date",
            "status",
            "validation_score",
            "source_urls",
            "published_at",
            "clauses",
        )


class AddressCheckRequestSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=255)
    city_code = serializers.ChoiceField(choices=["NYC", "LA", "SF"])
    context = serializers.JSONField(required=False, default=dict)


class AddressCheckSerializer(serializers.ModelSerializer):
    provenance = serializers.SerializerMethodField()

    class Meta:
        model = models.AddressCheck
        fields = (
            "id",
            "address",
            "city_code",
            "result_grade",
            "decision_mode",
            "blocker_flags",
            "required_actions",
            "evidence",
            "confidence",
            "created_at",
            "provenance",
        )

    def get_provenance(self, obj: models.AddressCheck) -> dict:
        if not obj.snapshot:
            return {"snapshot_id": None, "checksum": None, "source_urls": []}
        return {
            "snapshot_id": obj.snapshot.id,
            "checksum": obj.snapshot.checksum,
            "source_urls": obj.snapshot.source_urls,
        }


class PortfolioImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PortfolioImport
        fields = ("id", "original_filename", "row_count", "status", "report", "created_at")


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Alert
        fields = (
            "id",
            "city_code",
            "change_type",
            "impacted_listing_ids",
            "severity",
            "message",
            "status",
            "created_at",
        )


class CheckoutSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=["starter", "pro", "team"])
    success_url = serializers.URLField(required=False)
    cancel_url = serializers.URLField(required=False)


class AutonomyStatusSerializer(serializers.Serializer):
    city_snapshots = serializers.JSONField()
    recent_autonomy_events = serializers.JSONField()
    recent_rollbacks = serializers.JSONField()
    stale_cities = serializers.ListField(child=serializers.CharField())


class SLOMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.SLOMetric
        fields = (
            "metric_name",
            "metric_value",
            "target_value",
            "window_start",
            "window_end",
            "status",
        )


class DailyMaintenanceResultSerializer(serializers.Serializer):
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField()
    cities_processed = serializers.JSONField()
    snapshots_published = serializers.IntegerField()
    slo_metrics_count = serializers.IntegerField()
    recovery_actions = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["healthy", "degraded"])


class SupabaseStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["connected", "degraded", "not_configured"])
    db = serializers.JSONField()
    rest = serializers.JSONField()
