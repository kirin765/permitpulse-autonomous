from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.db.models import Avg
from django.utils import timezone

from permitpulse.constants import PLAN_QUOTAS
from permitpulse.models import AddressCheck, DecisionTrace, Organization, RuleClause, RuleSnapshot


class QuotaExceededError(Exception):
    pass


@dataclass
class DecisionInput:
    address: str
    city_code: str
    context: dict[str, Any]
    organization: Optional[Organization] = None


def _context_value(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _evaluate_leaf(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    field = condition.get("field")
    op = condition.get("op", "eq")
    value = condition.get("value")
    observed = _context_value(context, field) if field else None

    if op == "exists":
        return observed is not None
    if op == "eq":
        return observed == value
    if op == "neq":
        return observed != value
    if op == "in":
        return observed in (value or [])
    if op == "not_in":
        return observed not in (value or [])
    if op == "gte":
        return observed is not None and observed >= value
    if op == "lte":
        return observed is not None and observed <= value
    return False


def evaluate_condition(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    if not condition:
        return True

    if "all" in condition:
        return all(evaluate_condition(item, context) for item in condition["all"])
    if "any" in condition:
        return any(evaluate_condition(item, context) for item in condition["any"])
    if "not" in condition:
        return not evaluate_condition(condition["not"], context)
    return _evaluate_leaf(condition, context)


def _enforce_quota(organization: Optional[Organization]) -> None:
    if not organization:
        return
    plan = organization.plan.lower()
    quota = PLAN_QUOTAS.get(plan, PLAN_QUOTAS["starter"])
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage = organization.address_checks.filter(created_at__gte=month_start).count()
    if usage >= quota:
        raise QuotaExceededError(f"Monthly quota exceeded for plan '{organization.plan}'")


def run_address_decision(decision_input: DecisionInput) -> AddressCheck:
    _enforce_quota(decision_input.organization)

    snapshot = (
        RuleSnapshot.objects.filter(city_code=decision_input.city_code, is_active=True)
        .order_by("-version")
        .first()
    )

    if not snapshot:
        return AddressCheck.objects.create(
            organization=decision_input.organization,
            address=decision_input.address,
            city_code=decision_input.city_code,
            result_grade="UNDETERMINED",
            decision_mode="AUTO_CONSERVATIVE",
            blocker_flags=["no_active_snapshot"],
            required_actions=["Wait for next rule ingestion cycle."],
            evidence=[],
            confidence=0.0,
        )

    applicable_clauses: list[RuleClause] = []
    blockers: list[str] = []
    actions: list[str] = []
    evidence: list[dict[str, Any]] = []

    for clause in snapshot.clauses.all():
        if evaluate_condition(clause.condition_expr, decision_input.context):
            applicable_clauses.append(clause)
            evidence.append(
                {
                    "clause_id": clause.clause_id,
                    "category": clause.category,
                    "requirement_text": clause.requirement_text,
                    "penalty_text": clause.penalty_text,
                }
            )
            if clause.category.lower() in {"prohibition", "blocker"}:
                blockers.append(clause.requirement_text)
            elif clause.category.lower() in {"requirement", "registration", "tax"}:
                actions.append(clause.requirement_text)

    clause_confidence = (
        applicable_clauses and sum(clause.confidence for clause in applicable_clauses) / len(applicable_clauses)
    )
    confidence = float(clause_confidence or snapshot.validation_score)

    decision_mode = "AUTO_CONFIDENT"
    result_grade = "GREEN"
    if blockers:
        result_grade = "RED"
    elif actions:
        result_grade = "YELLOW"

    if (
        snapshot.status != "ACTIVE"
        or confidence < settings.PERMITPULSE_CONFIDENCE_THRESHOLD
        or snapshot.validation_score < settings.PERMITPULSE_CONFIDENCE_THRESHOLD
    ):
        decision_mode = "AUTO_CONSERVATIVE"
        if result_grade == "GREEN":
            result_grade = "UNDETERMINED"

    check = AddressCheck.objects.create(
        organization=decision_input.organization,
        address=decision_input.address,
        city_code=decision_input.city_code,
        result_grade=result_grade,
        decision_mode=decision_mode,
        blocker_flags=blockers,
        required_actions=actions,
        evidence=evidence,
        snapshot=snapshot,
        confidence=confidence,
    )

    DecisionTrace.objects.create(
        address_check=check,
        snapshot=snapshot,
        rule_ids=[clause.clause_id for clause in applicable_clauses],
        confidence=confidence,
    )
    return check
