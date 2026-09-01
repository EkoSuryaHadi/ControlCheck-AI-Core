from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from ..persistence.models import (
    AnalysisRunRecord,
    BudgetRecordRecord,
    CostRecordRecord,
    FindingEvidenceRecord,
    FindingRecord,
    HealthSnapshotRecord,
    ProgressRecordRecord,
    ScheduleActivityRecord,
    WBSNodeRecord,
)
from ..logging import get_logger

logger = get_logger("ai.tools")


def get_latest_run_id(organization_id: UUID, project_id: UUID, session: Session) -> UUID | None:
    return session.scalar(
        select(AnalysisRunRecord.id)
        .where(
            AnalysisRunRecord.organization_id == organization_id,
            AnalysisRunRecord.project_id == project_id,
            AnalysisRunRecord.status == "succeeded",
        )
        .order_by(AnalysisRunRecord.completed_at.desc(), AnalysisRunRecord.id.desc())
    )


def get_project_health(organization_id: UUID, project_id: UUID, session: Session) -> dict[str, Any]:
    """Retrieves the latest project health score, category breakdown, and score band."""
    logger.info("Tool called: get_project_health (project_id=%s)", project_id)
    snapshot = session.scalar(
        select(HealthSnapshotRecord)
        .where(
            HealthSnapshotRecord.organization_id == organization_id,
            HealthSnapshotRecord.project_id == project_id,
        )
        .order_by(HealthSnapshotRecord.created_at.desc(), HealthSnapshotRecord.id.desc())
    )
    if not snapshot:
        return {"status": "no_data", "message": "No health snapshot available for this project"}

    return {
        "overall_score": snapshot.overall_score,
        "score_band": snapshot.score_band,
        "cost_score": snapshot.cost_score,
        "schedule_score": snapshot.schedule_score,
        "progress_score": snapshot.progress_score,
        "dq_score": snapshot.dq_score,
        "component_breakdown": snapshot.component_breakdown,
        "key_drivers": snapshot.key_drivers,
        "calculated_at": snapshot.created_at.isoformat(),
    }


def get_top_cost_drivers(
    organization_id: UUID, project_id: UUID, session: Session, limit: int = 5
) -> list[dict[str, Any]]:
    """Retrieves top critical and warning cost findings for the latest project analysis."""
    logger.info("Tool called: get_top_cost_drivers (project_id=%s, limit=%d)", project_id, limit)
    run_id = get_latest_run_id(organization_id, project_id, session)
    if not run_id:
        return []

    findings = list(
        session.scalars(
            select(FindingRecord)
            .where(
                FindingRecord.organization_id == organization_id,
                FindingRecord.analysis_run_id == run_id,
                FindingRecord.category.in_(["COST", "DATA_QUALITY"]),
            )
            .order_by(case((FindingRecord.severity == "critical", 0), else_=1), FindingRecord.id)
            .limit(limit)
        )
    )

    return [
        {
            "finding_id": f.engine_finding_id,
            "rule_id": f.rule_id,
            "rule_name": f.rule_name,
            "entity_id": f.entity_id,
            "severity": f.severity,
            "title": f.title,
            "description": f.description,
            "business_impact": f.business_impact,
            "recommendation": f.recommendation,
            "metrics": f.metrics,
            "evidence": _evidence_for_record(f, session),
        }
        for f in findings
    ]


def get_delayed_activities(
    organization_id: UUID, project_id: UUID, session: Session
) -> list[dict[str, Any]]:
    """Retrieves overdue or critical schedule findings and delayed activities."""
    logger.info("Tool called: get_delayed_activities (project_id=%s)", project_id)
    run_id = get_latest_run_id(organization_id, project_id, session)
    if not run_id:
        return []

    findings = list(
        session.scalars(
            select(FindingRecord)
            .where(
                FindingRecord.organization_id == organization_id,
                FindingRecord.analysis_run_id == run_id,
                FindingRecord.category == "SCHEDULE",
            )
            .order_by(case((FindingRecord.severity == "critical", 0), else_=1), FindingRecord.id)
            .limit(10)
        )
    )

    return [
        {
            "finding_id": f.engine_finding_id,
            "rule_id": f.rule_id,
            "rule_name": f.rule_name,
            "activity_id": f.entity_id,
            "severity": f.severity,
            "title": f.title,
            "description": f.description,
            "business_impact": f.business_impact,
            "recommendation": f.recommendation,
            "metrics": f.metrics,
            "evidence": _evidence_for_record(f, session),
        }
        for f in findings
    ]



def _evidence_for_record(finding: FindingRecord, session: Session) -> list[dict[str, Any]]:
    """Return only persisted, source-addressable evidence for a finding."""
    return [
        {
            "source_sheet": item.source_sheet,
            "source_rows": item.source_rows,
            "record_ids": item.record_ids,
            "fields": item.fields,
            "aggregation": item.aggregation,
        }
        for item in session.scalars(
            select(FindingEvidenceRecord)
            .where(FindingEvidenceRecord.finding_id == finding.id)
            .order_by(FindingEvidenceRecord.evidence_order)
        )
    ]
def get_finding_evidence(
    organization_id: UUID, finding_id: UUID, session: Session
) -> list[dict[str, Any]]:
    """Retrieves verified evidence items for a specific finding."""
    logger.info("Tool called: get_finding_evidence (finding_id=%s)", finding_id)
    evidence_records = list(
        session.scalars(
            select(FindingEvidenceRecord)
            .join(FindingRecord, FindingRecord.id == FindingEvidenceRecord.finding_id)
            .where(
                FindingRecord.organization_id == organization_id,
                FindingEvidenceRecord.finding_id == finding_id,
            )
            .order_by(FindingEvidenceRecord.evidence_order)
        )
    )

    return [
        {
            "evidence_order": e.evidence_order,
            "source_sheet": e.source_sheet,
            "source_rows": e.source_rows,
            "record_ids": e.record_ids,
            "fields": e.fields,
            "aggregation": e.aggregation,
        }
        for e in evidence_records
    ]



