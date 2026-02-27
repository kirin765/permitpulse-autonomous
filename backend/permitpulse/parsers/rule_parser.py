from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup
from django.conf import settings
import requests

from permitpulse.connectors.city_sources import RawRuleDocument


@dataclass
class ParsedRuleDraft:
    checksum: str
    validation_score: float
    clauses: list[dict[str, Any]]
    source_urls: list[str]
    parser_traces: list[str]


def _normalize_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def _rule_based_extract(text: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    clauses: list[dict[str, Any]] = []

    if "register" in lowered or "registration" in lowered:
        clauses.append(
            {
                "clause_id": "registration-required",
                "category": "requirement",
                "condition_expr": {},
                "requirement_text": "Host registration is required before listing.",
                "penalty_text": "Listings may be removed if unregistered.",
                "confidence": 0.85,
            }
        )
    if "primary residence" in lowered:
        clauses.append(
            {
                "clause_id": "primary-residence",
                "category": "prohibition",
                "condition_expr": {
                    "not": {"field": "property.is_primary_residence", "op": "eq", "value": True}
                },
                "requirement_text": "Only primary residences may be rented short-term.",
                "penalty_text": "Non-primary homes are prohibited for STR operations.",
                "confidence": 0.82,
            }
        )
    if "tax" in lowered:
        clauses.append(
            {
                "clause_id": "tax-registration",
                "category": "tax",
                "condition_expr": {},
                "requirement_text": "Transient occupancy tax registration is required.",
                "penalty_text": "Financial penalties may apply for unpaid taxes.",
                "confidence": 0.78,
            }
        )

    if not clauses:
        clauses.append(
            {
                "clause_id": "fallback-manual-review-block",
                "category": "requirement",
                "condition_expr": {},
                "requirement_text": "Rules changed but parser confidence is low. Treat as restricted until next cycle.",
                "penalty_text": "Potential enforcement risk if operated without confirmation.",
                "confidence": 0.5,
            }
        )

    return clauses


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    chunks: list[str] = []
    for output_item in payload.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") in {"output_text", "text"} and isinstance(content_item.get("text"), str):
                chunks.append(content_item["text"])
    return "\n".join(chunks).strip()


def _llm_schema_extract(text: str) -> list[dict[str, Any]]:
    if not settings.OPENAI_API_KEY:
        return []
    schema = {
        "type": "object",
        "properties": {
            "clauses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "clause_id": {"type": "string"},
                        "category": {"type": "string"},
                        "condition_expr": {"type": "object"},
                        "requirement_text": {"type": "string"},
                        "penalty_text": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": [
                        "clause_id",
                        "category",
                        "condition_expr",
                        "requirement_text",
                        "penalty_text",
                        "confidence",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["clauses"],
        "additionalProperties": False,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4.1-mini",
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "Extract short-term rental regulations into normalized JSON clauses. "
                            "Use conservative confidence values."
                        ),
                    },
                    {
                        "role": "user",
                        "content": text[:20000],
                    },
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "str_rules",
                        "schema": schema,
                        "strict": True,
                    }
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        raw_text = _extract_response_text(payload)
        if not raw_text:
            return []
        parsed = json.loads(raw_text)
        clauses = parsed.get("clauses", [])
        if not isinstance(clauses, list):
            return []
        return [clause for clause in clauses if isinstance(clause, dict)]
    except Exception:  # noqa: BLE001
        return []


def parse_rule_document(document: RawRuleDocument) -> ParsedRuleDraft:
    normalized_text = _normalize_text(document.content)
    checksum = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    rule_based_clauses = _rule_based_extract(normalized_text)
    llm_clauses = _llm_schema_extract(normalized_text)

    merged = rule_based_clauses + [c for c in llm_clauses if c.get("clause_id") not in {x["clause_id"] for x in rule_based_clauses}]

    confidence_scores = [float(item.get("confidence", 0.0)) for item in merged]
    validation_score = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0

    return ParsedRuleDraft(
        checksum=checksum,
        validation_score=round(validation_score, 4),
        clauses=merged,
        source_urls=[document.source_url],
        parser_traces=["rule_based", "llm_schema_extract"],
    )
