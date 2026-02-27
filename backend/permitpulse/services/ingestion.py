from __future__ import annotations

from datetime import date
from typing import Optional

from django.db import transaction
from django.utils import timezone

from permitpulse.connectors.city_sources import fetch_city_document
from permitpulse.models import Alert, AutonomyEvent, Organization, RuleClause, RuleSnapshot
from permitpulse.parsers.rule_parser import parse_rule_document
from permitpulse.services.validation_gate import validate_parsed_rules


def _latest_snapshot(city_code: str) -> Optional[RuleSnapshot]:
    return RuleSnapshot.objects.filter(city_code=city_code, is_active=True).order_by("-version").first()


def _next_version(city_code: str) -> int:
    latest = RuleSnapshot.objects.filter(city_code=city_code).order_by("-version").first()
    return 1 if not latest else latest.version + 1


def _broadcast_alert(city_code: str, message: str, change_type: str = "rule_update") -> None:
    orgs = Organization.objects.all()
    alerts = [
        Alert(
            organization=org,
            city_code=city_code,
            change_type=change_type,
            impacted_listing_ids=[],
            severity="medium",
            message=message,
        )
        for org in orgs
    ]
    if alerts:
        Alert.objects.bulk_create(alerts)


def ingest_city_rules(city_code: str) -> Optional[RuleSnapshot]:
    previous = _latest_snapshot(city_code)

    try:
        document = fetch_city_document(city_code)
        draft = parse_rule_document(document)
        validation = validate_parsed_rules(city_code, draft, previous)

        if previous and previous.checksum == draft.checksum:
            AutonomyEvent.objects.create(
                event_type="data_loop",
                trigger=f"ingest:{city_code}",
                action_taken="skip_publish_same_checksum",
                outcome="stable",
                details={"city_code": city_code, "checksum": draft.checksum},
            )
            return previous

        if not validation.is_valid:
            if previous:
                previous.status = "STALE"
                previous.save(update_fields=["status", "updated_at"])
            AutonomyEvent.objects.create(
                event_type="data_loop",
                trigger=f"ingest:{city_code}",
                action_taken="hold_previous_snapshot",
                outcome="degraded",
                details={
                    "city_code": city_code,
                    "reasons": validation.reasons,
                    "validation_score": validation.validation_score,
                },
            )
            return previous

        with transaction.atomic():
            RuleSnapshot.objects.filter(city_code=city_code, is_active=True).update(is_active=False)
            snapshot = RuleSnapshot.objects.create(
                city_code=city_code,
                version=_next_version(city_code),
                checksum=draft.checksum,
                effective_date=date.today(),
                status="ACTIVE",
                validation_score=validation.validation_score,
                source_urls=draft.source_urls,
                parsed_payload={
                    "parser_traces": draft.parser_traces,
                    "clause_count": len(draft.clauses),
                },
                is_active=True,
                published_at=timezone.now(),
            )
            RuleClause.objects.bulk_create(
                [
                    RuleClause(
                        snapshot=snapshot,
                        clause_id=clause["clause_id"],
                        category=clause["category"],
                        condition_expr=clause.get("condition_expr", {}),
                        requirement_text=clause["requirement_text"],
                        penalty_text=clause.get("penalty_text", ""),
                        confidence=float(clause.get("confidence", 0.0)),
                    )
                    for clause in draft.clauses
                ]
            )

        _broadcast_alert(city_code, f"{city_code} regulatory rules were updated to version {snapshot.version}.")
        AutonomyEvent.objects.create(
            event_type="data_loop",
            trigger=f"ingest:{city_code}",
            action_taken="publish_new_snapshot",
            outcome="healthy",
            details={"city_code": city_code, "version": snapshot.version, "score": validation.validation_score},
        )
        return snapshot
    except Exception as exc:  # noqa: BLE001
        if previous:
            previous.status = "STALE"
            previous.save(update_fields=["status", "updated_at"])

        AutonomyEvent.objects.create(
            event_type="data_loop",
            trigger=f"ingest:{city_code}",
            action_taken="fallback_to_previous_snapshot",
            outcome="degraded",
            details={"error": str(exc), "city_code": city_code},
        )
        return previous
