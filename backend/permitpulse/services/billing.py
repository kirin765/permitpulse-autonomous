from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import stripe
from django.conf import settings
from django.db import transaction

from permitpulse.models import BillingEvent, CustomerPolicyAction, Organization


@dataclass
class CheckoutResult:
    session_id: str
    checkout_url: str


def _configure_stripe() -> bool:
    if not settings.STRIPE_SECRET_KEY:
        return False
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return True


def create_checkout_session(
    organization: Organization,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> CheckoutResult:
    if not _configure_stripe():
        mock_session_id = f"mock_{organization.slug}_{plan}"
        return CheckoutResult(
            session_id=mock_session_id,
            checkout_url=f"{settings.FRONTEND_ORIGIN}/billing/mock-checkout?session_id={mock_session_id}",
        )

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_IDS[plan], "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(organization.id),
        metadata={"org_slug": organization.slug, "plan": plan},
    )
    return CheckoutResult(session_id=session.id, checkout_url=session.url)


def _apply_payment_failure_policy(org: Optional[Organization], event: dict[str, Any]) -> dict[str, Any]:
    action = CustomerPolicyAction.objects.create(
        organization=org,
        action_type="payment_failed",
        policy_id="auto_grace_period_v1",
        input_event=event,
        result={"grace_days": 3, "status": "grace_applied"},
    )
    return action.result


def _apply_refund_policy(org: Optional[Organization], event: dict[str, Any]) -> dict[str, Any]:
    action = CustomerPolicyAction.objects.create(
        organization=org,
        action_type="refund_processed",
        policy_id="auto_refund_ack_v1",
        input_event=event,
        result={"status": "refund_acknowledged"},
    )
    return action.result


def _upgrade_plan_if_needed(org: Optional[Organization], event: dict[str, Any]) -> dict[str, Any]:
    if not org:
        return {"status": "org_not_found"}
    metadata = event.get("data", {}).get("object", {}).get("metadata", {})
    plan = metadata.get("plan")
    if plan in settings.STRIPE_PRICE_IDS:
        org.plan = plan
        org.save(update_fields=["plan", "updated_at"])
        return {"status": "upgraded", "plan": plan}
    return {"status": "no_change"}


def process_webhook(payload: bytes, signature_header: Optional[str] = None) -> Tuple[dict[str, Any], int]:
    event: dict[str, Any]
    if settings.STRIPE_SECRET_KEY and settings.STRIPE_WEBHOOK_SECRET:
        try:
            event_obj = stripe.Webhook.construct_event(payload, signature_header, settings.STRIPE_WEBHOOK_SECRET)
            event = event_obj.to_dict_recursive()
        except Exception as exc:  # noqa: BLE001
            return {"detail": f"Invalid webhook: {exc}"}, 400
    else:
        import json

        event = json.loads(payload.decode("utf-8"))

    event_id = event.get("id") or event.get("request", {}).get("id") or "local-event"
    event_type = event.get("type", "unknown")
    org_slug = event.get("data", {}).get("object", {}).get("metadata", {}).get("org_slug")
    org = Organization.objects.filter(slug=org_slug).first() if org_slug else None

    with transaction.atomic():
        bill_event, created = BillingEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={
                "organization": org,
                "event_type": event_type,
                "payload": event,
                "processed": False,
            },
        )
        if not created and bill_event.processed:
            return {"status": "duplicate_ignored"}, 200

        result: dict[str, Any] = {"status": "ignored"}
        if event_type == "invoice.payment_failed":
            result = _apply_payment_failure_policy(org, event)
        elif event_type == "charge.refunded":
            result = _apply_refund_policy(org, event)
        elif event_type == "checkout.session.completed":
            result = _upgrade_plan_if_needed(org, event)

        bill_event.processed = True
        bill_event.event_type = event_type
        bill_event.payload = event
        bill_event.organization = org
        bill_event.save(update_fields=["processed", "event_type", "payload", "organization", "updated_at"])

    return {"status": "processed", "result": result}, 200
