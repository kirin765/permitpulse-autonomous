from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from permitpulse.models import RuleSnapshot
from permitpulse.parsers.rule_parser import ParsedRuleDraft


@dataclass
class ValidationResult:
    is_valid: bool
    validation_score: float
    reasons: list[str] = field(default_factory=list)


def validate_parsed_rules(
    city_code: str,
    draft: ParsedRuleDraft,
    previous: Optional[RuleSnapshot],
) -> ValidationResult:
    reasons: list[str] = []

    if not draft.clauses:
        reasons.append("no_clauses")

    for clause in draft.clauses:
        for required_key in ("clause_id", "category", "requirement_text", "confidence"):
            if required_key not in clause:
                reasons.append(f"missing:{required_key}")

    if previous:
        old_len = previous.clauses.count()
        new_len = len(draft.clauses)
        if old_len > 0:
            ratio = new_len / old_len
            if ratio > 3.0 or ratio < 0.33:
                reasons.append("diff_sanity_failed")

    if draft.validation_score < 0.5:
        reasons.append("low_validation_score")

    return ValidationResult(
        is_valid=len(reasons) == 0,
        validation_score=draft.validation_score,
        reasons=reasons,
    )
