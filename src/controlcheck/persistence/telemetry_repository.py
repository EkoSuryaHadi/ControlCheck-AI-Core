from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..telemetry import sanitize_event_metadata, validate_event_name
from .models import FindingFeedbackRecord, ProductEventRecord


class TelemetryRepository:
    def __init__(self, session: Session):
        self.session = session

    def record_event(
        self,
        *,
        organization_id: UUID,
        event_name: str,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        analysis_run_id: UUID | None = None,
        finding_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> ProductEventRecord:
        record = ProductEventRecord(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            finding_id=finding_id,
            event_name=validate_event_name(event_name),
            metadata_json=sanitize_event_metadata(metadata),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def add_feedback(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        analysis_run_id: UUID,
        rating: str,
        finding_id: UUID | None = None,
        comment: str | None = None,
        user_id: UUID | None = None,
    ) -> FindingFeedbackRecord:
        feedback = FindingFeedbackRecord(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            finding_id=finding_id,
            rating=rating,
            comment=comment.strip() if comment else None,
        )
        self.session.add(feedback)
        self.session.flush()
        return feedback

    def metrics(self, organization_id: UUID) -> dict:
        def count_events(name: str | None = None) -> int:
            stmt = select(func.count(ProductEventRecord.id)).where(ProductEventRecord.organization_id == organization_id)
            if name:
                stmt = stmt.where(ProductEventRecord.event_name == name)
            return int(self.session.scalar(stmt) or 0)

        registrations = count_events("registration_completed")
        active_users = int(self.session.scalar(
            select(func.count(func.distinct(ProductEventRecord.user_id))).where(
                ProductEventRecord.organization_id == organization_id,
                ProductEventRecord.user_id.is_not(None),
            )
        ) or 0)
        projects = int(self.session.scalar(
            select(func.count(func.distinct(ProductEventRecord.project_id))).where(
                ProductEventRecord.organization_id == organization_id,
                ProductEventRecord.project_id.is_not(None),
            )
        ) or 0)
        uploads = count_events("upload_accepted")
        analyses = count_events("analysis_completed")
        result_use = sum(count_events(name) for name in ("finding_viewed", "evidence_viewed", "finding_exported", "run_feedback_submitted", "finding_feedback_submitted"))
        feedback_count = int(self.session.scalar(select(func.count(FindingFeedbackRecord.id)).where(FindingFeedbackRecord.organization_id == organization_id)) or 0)
        useful_count = int(self.session.scalar(select(func.count(FindingFeedbackRecord.id)).where(FindingFeedbackRecord.organization_id == organization_id, FindingFeedbackRecord.rating == "useful")) or 0)
        total_requests = count_events("upload_accepted") + count_events("upload_failed") + count_events("analysis_completed") + count_events("analysis_failed")
        failures = count_events("upload_failed") + count_events("analysis_failed")
        return {
            "registrations": registrations,
            "active_users": active_users,
            "projects": projects,
            "uploads_accepted": uploads,
            "analyses_completed": analyses,
            "result_use_events": result_use,
            "result_use_rate": round(result_use / analyses, 4) if analyses else 0.0,
            "feedback_count": feedback_count,
            "useful_feedback_rate": round(useful_count / feedback_count, 4) if feedback_count else 0.0,
            "error_rate": round(failures / total_requests, 4) if total_requests else 0.0,
            "generated_at": datetime.now(timezone.utc),
        }
