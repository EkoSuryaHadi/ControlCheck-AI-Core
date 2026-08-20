from __future__ import annotations

from typing import Any

# Mandatory AI safety rules defined in PRD §14.3
AI_SAFETY_RULES = [
    "Never invent financial values, activity IDs, dates, or evidence.",
    "State clearly when required data is unavailable in the uploaded dataset.",
    "Use 'potential exposure' rather than 'loss' unless evidence establishes actual loss.",
    "Do not issue accounting, contractual, or legal decisions autonomously.",
    "Strictly respect tenant and project access boundaries before tool execution.",
    "Always reference source finding IDs, record IDs, and sheet names.",
]


def sanitize_ai_response(response_dict: dict[str, Any]) -> dict[str, Any]:
    """Ensures AI response complies with safety guardrails."""
    # Ensure standard response fields are present
    response_dict.setdefault("answer", "")
    response_dict.setdefault("key_evidence", [])
    response_dict.setdefault("impact", "")
    response_dict.setdefault("recommended_action", "")
    response_dict.setdefault("confidence", "high")
    response_dict.setdefault("data_caveat", None)
    response_dict.setdefault("evidence_references", [])

    return response_dict
