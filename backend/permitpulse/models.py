from __future__ import annotations

from django.db import models
from django.utils import timezone

from permitpulse.constants import CITY_CHOICES, DECISION_MODES, RESULT_GRADES, SNAPSHOT_STATUS


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimestampedModel):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    billing_email = models.EmailField(blank=True)
    plan = models.CharField(max_length=32, default="starter")

    def __str__(self) -> str:
        return self.slug


class RuleSnapshot(TimestampedModel):
    city_code = models.CharField(max_length=8, choices=CITY_CHOICES)
    version = models.PositiveIntegerField()
    checksum = models.CharField(max_length=128)
    effective_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=16, choices=SNAPSHOT_STATUS, default="ACTIVE")
    validation_score = models.FloatField(default=0.0)
    source_urls = models.JSONField(default=list)
    parsed_payload = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("city_code", "version")
        ordering = ["-published_at"]


class RuleClause(TimestampedModel):
    snapshot = models.ForeignKey(RuleSnapshot, related_name="clauses", on_delete=models.CASCADE)
    clause_id = models.CharField(max_length=64)
    category = models.CharField(max_length=32)
    condition_expr = models.JSONField(default=dict)
    requirement_text = models.TextField()
    penalty_text = models.TextField(blank=True)
    confidence = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict)

    class Meta:
        unique_together = ("snapshot", "clause_id")


class AddressCheck(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        related_name="address_checks",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    address = models.CharField(max_length=255)
    city_code = models.CharField(max_length=8, choices=CITY_CHOICES)
    result_grade = models.CharField(max_length=16, choices=RESULT_GRADES, default="UNDETERMINED")
    decision_mode = models.CharField(max_length=32, choices=DECISION_MODES, default="AUTO_CONSERVATIVE")
    blocker_flags = models.JSONField(default=list)
    required_actions = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    snapshot = models.ForeignKey(
        RuleSnapshot,
        related_name="address_checks",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    confidence = models.FloatField(default=0.0)


class DecisionTrace(TimestampedModel):
    address_check = models.OneToOneField(
        AddressCheck,
        related_name="decision_trace",
        on_delete=models.CASCADE,
    )
    snapshot = models.ForeignKey(RuleSnapshot, related_name="decision_traces", on_delete=models.PROTECT)
    rule_ids = models.JSONField(default=list)
    confidence = models.FloatField(default=0.0)
    generated_at = models.DateTimeField(default=timezone.now)


class PortfolioImport(TimestampedModel):
    organization = models.ForeignKey(Organization, related_name="portfolio_imports", on_delete=models.CASCADE)
    original_filename = models.CharField(max_length=255)
    row_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, default="completed")
    report = models.JSONField(default=dict)


class Alert(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        related_name="alerts",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    city_code = models.CharField(max_length=8, choices=CITY_CHOICES)
    change_type = models.CharField(max_length=64)
    impacted_listing_ids = models.JSONField(default=list)
    severity = models.CharField(max_length=16, default="medium")
    message = models.TextField()
    status = models.CharField(max_length=16, default="new")


class BillingEvent(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        related_name="billing_events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    stripe_event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)


class AutonomyEvent(TimestampedModel):
    event_type = models.CharField(max_length=64)
    trigger = models.CharField(max_length=128)
    action_taken = models.CharField(max_length=255)
    outcome = models.CharField(max_length=64)
    details = models.JSONField(default=dict)


class RollbackEvent(TimestampedModel):
    failed_release = models.CharField(max_length=128)
    fallback_release = models.CharField(max_length=128)
    reason = models.TextField()
    recovered_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict)


class CustomerPolicyAction(TimestampedModel):
    organization = models.ForeignKey(
        Organization,
        related_name="policy_actions",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    action_type = models.CharField(max_length=64)
    policy_id = models.CharField(max_length=64)
    input_event = models.JSONField(default=dict)
    result = models.JSONField(default=dict)


class SLOMetric(TimestampedModel):
    metric_name = models.CharField(max_length=64)
    metric_value = models.FloatField(default=0.0)
    target_value = models.FloatField(default=0.0)
    window_start = models.DateTimeField(default=timezone.now)
    window_end = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, default="healthy")

    class Meta:
        ordering = ["-window_end"]
