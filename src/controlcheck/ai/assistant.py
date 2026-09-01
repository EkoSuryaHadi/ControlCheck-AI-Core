from __future__ import annotations

from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session

from .safety import sanitize_ai_response
from .tools import (
    get_delayed_activities,
    get_finding_evidence,
    get_project_health,
    get_top_cost_drivers,
)
from ..logging import get_logger

logger = get_logger("ai.assistant")


def _grounding(items: list[dict[str, Any]]) -> tuple[str, str | None]:
    """Derive confidence from persisted evidence availability."""
    if not items:
        return "high", None
    grounded = [item for item in items if item.get("evidence")]
    if len(grounded) == len(items):
        return "high", None
    return "medium", "Some findings do not have persisted evidence references; verify the source records before acting."


class ProjectAIAssistant:
    """Deterministic, tool-grounded AI reasoning assistant for project-control audits."""

    def __init__(self, organization_id: UUID, project_id: UUID, session: Session):
        self.organization_id = organization_id
        self.project_id = project_id
        self.session = session

    def ask(self, question: str) -> dict[str, Any]:
        """Processes a natural language question using controlled tools and deterministic reasoning."""
        q_lower = question.lower()
        logger.info("AI Assistant received question: '%s'", question)

        # 1. Schedule & Delays Intent
        if any(keyword in q_lower for keyword in ["delay", "schedule", "overdue", "late", "timeline", "milestone"]):
            delayed = get_delayed_activities(self.organization_id, self.project_id, self.session)
            if not delayed:
                return sanitize_ai_response({
                    "answer": "No critical schedule delays or overdue activities were detected in the latest audit run.",
                    "key_evidence": [],
                    "impact": "Schedule performance is aligned with baseline thresholds.",
                    "recommended_action": "Continue monitoring periodic progress updates against baseline finish dates.",
                    "confidence": "high",
                    "data_caveat": None,
                    "evidence_references": [],
                })

            top_item = delayed[0]
            confidence, caveat = _grounding(delayed)
            answer = (
                f"Detected {len(delayed)} schedule issue(s). Key delayed activity is '{top_item.get('activity_id')}' "
                f"({top_item.get('title')}). Description: {top_item.get('description')}."
            )
            return sanitize_ai_response({
                "answer": answer,
                "key_evidence": delayed[:3],
                "impact": top_item.get("business_impact", "Potential project handover delay."),
                "recommended_action": top_item.get("recommendation", "Review critical path and expedite pending milestones."),
                "confidence": "high",
                "data_caveat": None,
                "evidence_references": [d["finding_id"] for d in delayed if "finding_id" in d],
            })

        # 2. Cost, Budget, or Overrun Intent
        if any(keyword in q_lower for keyword in ["cost", "budget", "spend", "overrun", "variance", "expense", "vendor", "po"]):
            cost_drivers = get_top_cost_drivers(self.organization_id, self.project_id, self.session, limit=5)
            if not cost_drivers:
                return sanitize_ai_response({
                    "answer": "No material cost overruns or budget anomalies were detected in the latest analysis.",
                    "key_evidence": [],
                    "impact": "Costs are tracking within authorized budget limits.",
                    "recommended_action": "Maintain routine monthly commitment and invoice reconciliation.",
                    "confidence": "high",
                    "data_caveat": None,
                    "evidence_references": [],
                })

            top_cost = cost_drivers[0]
            confidence, caveat = _grounding(cost_drivers)
            answer = (
                f"Found {len(cost_drivers)} significant cost finding(s). The highest impact item is "
                f"'{top_cost.get('finding_id')}' on entity {top_cost.get('entity_id')}: {top_cost.get('title')}."
            )
            return sanitize_ai_response({
                "answer": answer,
                "key_evidence": cost_drivers[:3],
                "impact": top_cost.get("business_impact", "Potential cost overrun risk."),
                "recommended_action": top_cost.get("recommendation", "Investigate high-value invoices and commitments against WBS budget."),
                "confidence": "high",
                "data_caveat": None,
                "evidence_references": [c["finding_id"] for c in cost_drivers if "finding_id" in c],
            })

        # 3. Project Health & Summary Intent (Default)
        health = get_project_health(self.organization_id, self.project_id, self.session)
        if health.get("status") == "no_data":
            return sanitize_ai_response({
                "answer": "There is no completed analysis run available for this project yet. Please upload a project workbook first.",
                "key_evidence": [],
                "impact": "Unable to calculate project health metrics.",
                "recommended_action": "Upload an Excel workbook (.xlsx) to run the initial project-control evaluation.",
                "confidence": "high",
                "data_caveat": "Missing dataset snapshot.",
                "evidence_references": [],
            })

        score = health.get("overall_score", 0.0)
        band = health.get("score_band", "Unknown")
        c_score = health.get("cost_score", 100.0)
        s_score = health.get("schedule_score", 100.0)
        p_score = health.get("progress_score", 100.0)
        dq_score = health.get("dq_score", 100.0)

        answer = (
            f"The overall project health score is {score:.1f}/100, classified as '{band}'. "
            f"Breakdown: Cost={c_score:.1f}, Schedule={s_score:.1f}, Progress={p_score:.1f}, Data Quality={dq_score:.1f}."
        )

        drivers = health.get("key_drivers", [])
        confidence, caveat = _grounding(drivers)
        return sanitize_ai_response({
            "answer": answer,
            "key_evidence": drivers[:3],
            "impact": f"Project status is {band} based on deterministic evaluation of cost, schedule, and data quality rules.",
            "recommended_action": "Focus remediation on the lowest scoring domains identified in the breakdown.",
            "confidence": "high",
            "data_caveat": None,
            "evidence_references": [str(d.get("finding_id", "")) for d in drivers if isinstance(d, dict) and d.get("finding_id")],
        })

