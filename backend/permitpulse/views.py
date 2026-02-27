from __future__ import annotations

import csv
import io
from typing import Optional

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from permitpulse.models import AddressCheck, Alert, AutonomyEvent, Organization, RuleSnapshot
from permitpulse.serializers import (
    AddressCheckRequestSerializer,
    AddressCheckSerializer,
    AlertSerializer,
    CheckoutSerializer,
    DailyMaintenanceResultSerializer,
    PortfolioImportSerializer,
    RuleSnapshotSerializer,
    SupabaseStatusSerializer,
)
from permitpulse.services.billing import create_checkout_session, process_webhook
from permitpulse.services.decision_engine import DecisionInput, QuotaExceededError, run_address_decision
from permitpulse.services.maintenance import run_daily_maintenance
from permitpulse.services.runbook import autonomy_status_payload
from permitpulse.services.slo import latest_slo_summary
from permitpulse.services.supabase import supabase_status_payload


def _resolve_organization(request: Request) -> Optional[Organization]:
    if getattr(request, "organization", None):
        return request.organization
    org_slug = request.query_params.get("org")
    if org_slug:
        return Organization.objects.filter(slug=org_slug).first()
    return None


class AddressCheckCreateView(APIView):
    def post(self, request: Request) -> Response:
        serializer = AddressCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        org = _resolve_organization(request)

        try:
            check = run_address_decision(
                DecisionInput(
                    address=payload["address"],
                    city_code=payload["city_code"],
                    context=payload.get("context", {}),
                    organization=org,
                )
            )
        except QuotaExceededError as exc:
            return Response({"detail": str(exc)}, status=402)

        AutonomyEvent.objects.create(
            event_type="decision_loop",
            trigger="api:address_checks",
            action_taken="evaluate_address",
            outcome="healthy" if check.decision_mode == "AUTO_CONFIDENT" else "degraded",
            details={"check_id": check.id, "city_code": check.city_code},
        )
        return Response(AddressCheckSerializer(check).data, status=status.HTTP_201_CREATED)


class AddressCheckDetailView(APIView):
    def get(self, request: Request, check_id: int) -> Response:
        check = get_object_or_404(AddressCheck, id=check_id)
        return Response(AddressCheckSerializer(check).data)


class PortfolioImportView(APIView):
    def post(self, request: Request) -> Response:
        org = _resolve_organization(request)
        if not org:
            return Response({"detail": "Organization is required via X-Org-Slug or ?org=slug"}, status=400)

        csv_file = request.FILES.get("file")
        if not csv_file:
            return Response({"detail": "CSV file is required as 'file'"}, status=400)

        decoded = csv_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))

        rows = list(reader)
        outcomes = {"GREEN": 0, "YELLOW": 0, "RED": 0, "UNDETERMINED": 0}

        for row in rows:
            city_code = (row.get("city_code") or "NYC").strip().upper()
            address = (row.get("address") or "").strip()
            if not address:
                continue
            context = {
                "property": {
                    "is_primary_residence": (row.get("is_primary_residence", "").lower() in {"1", "true", "yes"})
                }
            }
            try:
                check = run_address_decision(
                    DecisionInput(address=address, city_code=city_code, context=context, organization=org)
                )
                outcomes[check.result_grade] += 1
            except QuotaExceededError:
                break

        portfolio_import = org.portfolio_imports.create(
            original_filename=csv_file.name,
            row_count=len(rows),
            status="completed",
            report={"result_counts": outcomes, "processed_at": timezone.now().isoformat()},
        )
        return Response(PortfolioImportSerializer(portfolio_import).data, status=201)


class CityRulesLatestView(APIView):
    def get(self, request: Request, city_code: str) -> Response:
        snapshot = (
            RuleSnapshot.objects.filter(city_code=city_code.upper(), is_active=True)
            .order_by("-version")
            .first()
        )
        if not snapshot:
            return Response({"detail": "No active snapshot found"}, status=404)
        return Response(RuleSnapshotSerializer(snapshot).data)


class AlertsListView(APIView):
    def get(self, request: Request) -> Response:
        org = _resolve_organization(request)
        queryset = Alert.objects.all().order_by("-created_at")
        if org:
            queryset = queryset.filter(organization=org)
        serializer = AlertSerializer(queryset[:100], many=True)
        return Response(serializer.data)


class CheckoutSessionView(APIView):
    def post(self, request: Request) -> Response:
        org = _resolve_organization(request)
        if not org:
            return Response({"detail": "Organization is required via X-Org-Slug or ?org=slug"}, status=400)

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        success_url = payload.get("success_url") or f"{settings.FRONTEND_ORIGIN}/billing/success"
        cancel_url = payload.get("cancel_url") or f"{settings.FRONTEND_ORIGIN}/billing/cancel"

        session = create_checkout_session(org, payload["plan"], success_url, cancel_url)
        return Response({"session_id": session.session_id, "checkout_url": session.checkout_url}, status=201)


class BillingWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request: Request) -> Response:
        payload = request.body
        signature = request.headers.get("Stripe-Signature")
        result, code = process_webhook(payload, signature)
        return Response(result, status=code)


class AutonomyStatusView(APIView):
    def get(self, request: Request) -> Response:
        return Response(autonomy_status_payload())


class SLOView(APIView):
    def get(self, request: Request) -> Response:
        return Response(latest_slo_summary())


class SupabaseStatusView(APIView):
    def get(self, request: Request) -> Response:
        serializer = SupabaseStatusSerializer(data=supabase_status_payload())
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class DailyMaintenanceCronView(APIView):
    authentication_classes = []
    permission_classes = []

    def _authorized(self, request: Request) -> bool:
        shared_secret = settings.CRON_SHARED_SECRET
        auth_header = request.headers.get("Authorization", "")
        token = ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

        # Vercel Cron on Hobby calls by schedule and includes the x-vercel-cron header.
        vercel_cron_header = request.headers.get("X-Vercel-Cron", "")

        if shared_secret and token == shared_secret:
            return True
        if request.method == "GET" and vercel_cron_header:
            return True
        return False

    def post(self, request: Request) -> Response:
        if not self._authorized(request):
            return Response({"detail": "Unauthorized cron request"}, status=401)
        serializer = DailyMaintenanceResultSerializer(data=run_daily_maintenance())
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=200)

    def get(self, request: Request) -> Response:
        if not self._authorized(request):
            return Response({"detail": "Unauthorized cron request"}, status=401)
        serializer = DailyMaintenanceResultSerializer(data=run_daily_maintenance())
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=200)
