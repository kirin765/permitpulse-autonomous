from django.contrib import admin

from permitpulse import models


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("slug", "plan", "billing_email", "created_at")


@admin.register(models.RuleSnapshot)
class RuleSnapshotAdmin(admin.ModelAdmin):
    list_display = ("city_code", "version", "status", "validation_score", "is_active")
    list_filter = ("city_code", "status", "is_active")


@admin.register(models.AddressCheck)
class AddressCheckAdmin(admin.ModelAdmin):
    list_display = ("id", "city_code", "result_grade", "decision_mode", "confidence", "created_at")
    list_filter = ("city_code", "result_grade", "decision_mode")


admin.site.register(models.RuleClause)
admin.site.register(models.DecisionTrace)
admin.site.register(models.PortfolioImport)
admin.site.register(models.Alert)
admin.site.register(models.BillingEvent)
admin.site.register(models.AutonomyEvent)
admin.site.register(models.RollbackEvent)
admin.site.register(models.CustomerPolicyAction)
admin.site.register(models.SLOMetric)
