"""Repository for the analysis_jobs queue consumed by the VPS Celery worker."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .models import AnalysisJobRecord


class AnalysisJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_job(
        self,
        organization_id: UUID,
        project_id: UUID,
        *,
        storage_key: str,
        filename: str,
        content_type: str,
        file_size_bytes: int,
        workbook_sha256: str | None = None,
    ) -> AnalysisJobRecord:
        job = AnalysisJobRecord(
            organization_id=organization_id,
            project_id=project_id,
            storage_key=storage_key,
            filename=filename,
            content_type=content_type,
            file_size_bytes=file_size_bytes,
            workbook_sha256=workbook_sha256,
            status="queued",
            attempts=0,
        )
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, organization_id: UUID, job_id: UUID) -> AnalysisJobRecord | None:
        return self.session.execute(
            select(AnalysisJobRecord).where(
                AnalysisJobRecord.organization_id == organization_id,
                AnalysisJobRecord.id == job_id,
            )
        ).scalar_one_or_none()

    def get_job_by_id(self, job_id: UUID) -> AnalysisJobRecord | None:
        """Worker-side lookup without an organization guard."""
        return self.session.execute(
            select(AnalysisJobRecord).where(AnalysisJobRecord.id == job_id)
        ).scalar_one_or_none()

    def requeue(self, job_id: UUID) -> None:
        """Release a claimed job back to ``queued`` for a later retry."""
        self.session.execute(
            update(AnalysisJobRecord)
            .where(AnalysisJobRecord.id == job_id)
            .values(status="queued", started_at=None)
        )
        self.session.commit()

    def recover_stale(self, grace_minutes: int = 30) -> int:
        """Reset ``processing`` jobs started more than ``grace_minutes`` ago
        (worker died mid-flight) back to ``queued``. Returns recovered count."""
        from datetime import timedelta

        from sqlalchemy import update

        stale_before = datetime.now(timezone.utc) - timedelta(minutes=grace_minutes)
        result = self.session.execute(
            update(AnalysisJobRecord)
            .where(
                AnalysisJobRecord.status == "processing",
                AnalysisJobRecord.started_at < stale_before,
            )
            .values(status="queued", started_at=None)
        )
        self.session.commit()
        return int(result.rowcount or 0)

    def list_jobs(
        self,
        organization_id: UUID,
        project_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AnalysisJobRecord], int]:
        base = select(AnalysisJobRecord).where(
            AnalysisJobRecord.organization_id == organization_id,
            AnalysisJobRecord.project_id == project_id,
        )
        total = self.session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
        rows = self.session.execute(
            base.order_by(AnalysisJobRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).scalars().all()
        return list(rows), int(total)

    def list_queued_ids(self, organization_id: UUID | None = None, limit: int = 10) -> list[UUID]:
        """Return queued job ids oldest-first, for the Celery beat poller."""
        query = (
            select(AnalysisJobRecord.id)
            .where(AnalysisJobRecord.status == "queued")
            .order_by(AnalysisJobRecord.created_at.asc())
            .limit(limit)
        )
        if organization_id is not None:
            query = query.where(AnalysisJobRecord.organization_id == organization_id)
        return list(self.session.execute(query).scalars().all())

    def claim_job(self, job_id: UUID) -> AnalysisJobRecord | None:
        """Atomically claim a queued job (row lock + status guard). Returns the
        claimed row, or None when it is already claimed/completed/failed."""
        row = self.session.execute(
            select(AnalysisJobRecord)
            .where(
                AnalysisJobRecord.id == job_id,
                AnalysisJobRecord.status == "queued",
            )
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if row is None:
            return None
        now = datetime.now(timezone.utc)
        row.status = "processing"
        row.started_at = now
        row.attempts += 1
        self.session.commit()
        return row

    def mark_completed(self, job_id: UUID, analysis_run_id: UUID) -> None:
        self.session.execute(
            update(AnalysisJobRecord)
            .where(AnalysisJobRecord.id == job_id)
            .values(
                status="completed",
                analysis_run_id=analysis_run_id,
                completed_at=datetime.now(timezone.utc),
            )
        )
        self.session.commit()

    def mark_failed(self, job_id: UUID, code: str, message: str) -> None:
        self.session.execute(
            update(AnalysisJobRecord)
            .where(AnalysisJobRecord.id == job_id)
            .values(
                status="failed",
                error_code=code[:80],
                error_message=message[:4000],
                completed_at=datetime.now(timezone.utc),
            )
        )
        self.session.commit()
