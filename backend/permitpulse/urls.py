from django.urls import path

from permitpulse import views

urlpatterns = [
    path("address-checks", views.AddressCheckCreateView.as_view(), name="address-check-create"),
    path("address-checks/<int:check_id>", views.AddressCheckDetailView.as_view(), name="address-check-detail"),
    path("portfolio/import", views.PortfolioImportView.as_view(), name="portfolio-import"),
    path("cities/<str:city_code>/rules/latest", views.CityRulesLatestView.as_view(), name="city-rules-latest"),
    path("alerts", views.AlertsListView.as_view(), name="alerts-list"),
    path("billing/checkout-session", views.CheckoutSessionView.as_view(), name="checkout-session"),
    path("billing/webhook", views.BillingWebhookView.as_view(), name="billing-webhook"),
    path(
        "internal/cron/daily-maintenance",
        views.DailyMaintenanceCronView.as_view(),
        name="daily-maintenance-cron",
    ),
    path("system/autonomy-status", views.AutonomyStatusView.as_view(), name="autonomy-status"),
    path("system/slo", views.SLOView.as_view(), name="system-slo"),
]
