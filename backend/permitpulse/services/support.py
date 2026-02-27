from __future__ import annotations

from permitpulse.models import CustomerPolicyAction


def auto_support_response(ticket_payload: dict) -> dict:
    category = ticket_payload.get("category", "general")
    templates = {
        "billing": "Billing issue received. Automatic policy checks are running.",
        "compliance": "Compliance question received. Latest rule snapshot evidence is attached automatically.",
        "general": "Request received. An automated workflow has started.",
    }
    message = templates.get(category, templates["general"])
    action = CustomerPolicyAction.objects.create(
        organization=None,
        action_type="support_auto_response",
        policy_id="support_template_v1",
        input_event=ticket_payload,
        result={"message": message, "category": category},
    )
    return action.result
