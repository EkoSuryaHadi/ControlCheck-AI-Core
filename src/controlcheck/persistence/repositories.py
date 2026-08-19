from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from .models import (
    AnalysisRunRecord,
    DatasetSnapshotRecord,
    FindingEvidenceRecord,
    FindingRecord,
    OrganizationRecord,
    ProjectRecord,
    RuleCatalogueVersionRecord,
    SourceFileRecord,
    AuditLogRecord,
)
from ..models import AuditResult, ProjectDataset
from ..storage import StoredObject


class OrganizationRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, organization_id: UUID) -> OrganizationRecord | None:
        return self.session.scalar(
            select(OrganizationRecord).where(OrganizationRecord.id == organization_id)
        )


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        organization_id: UUID,
        code: str,
        name: str,
        currency: str,
    ) -> ProjectRecord:
        project = ProjectRecord(
            organization_id=organization_id,
            code=code,
            name=name,
            currency=currency,
        )
        self.session.add(project)
        self.session.flush()
        return project

    def list_for_organization(self, organization_id: UUID) -> list[ProjectRecord]:
        return list(
            self.session.scalars(
                select(ProjectRecord)
                .where(ProjectRecord.organization_id == organization_id)
                .order_by(ProjectRecord.created_at, ProjectRecord.id)
            )
        )

    def get_scoped(self, organization_id: UUID, project_id: UUID) -> ProjectRecord | None:
        return self.session.scalar(
            select(ProjectRecord).where(
                ProjectRecord.id == project_id,
                ProjectRecord.organization_id == organization_id,
            )
        )


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_or_create_catalogue(
        self, version: str, sha256: str, definition: dict
    ) -> RuleCatalogueVersionRecord:
        record = self.session.scalar(
            select(RuleCatalogueVersionRecord).where(
                RuleCatalogueVersionRecord.version == version,
                RuleCatalogueVersionRecord.sha256 == sha256,
            )
        )
        if record is None:
            record = RuleCatalogueVersionRecord(
                version=version, sha256=sha256, definition=definition
            )
            self.session.add(record)
            self.session.flush()
        return record

    def start_run(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        mime_type: str,
        stored: StoredObject,
        dataset: ProjectDataset,
        catalogue: RuleCatalogueVersionRecord,
        engine_version: str,
    ) -> AnalysisRunRecord:
        source = SourceFileRecord(
            organization_id=organization_id,
            project_id=project_id,
            file_name=filename,
            storage_key=stored.key,
            mime_type=mime_type,
            file_size_bytes=stored.size_bytes,
            sha256=stored.sha256,
        )
        self.session.add(source)
        self.session.flush()
        snapshot = DatasetSnapshotRecord(
            organization_id=organization_id,
            project_id=project_id,
            source_file_id=source.id,
            dataset_version=dataset.dataset_version,
            data_date=dataset.data_date,
            source_project_id=dataset.project.project_id,
            status="validated",
        )
        self.session.add(snapshot)
        self.session.flush()
        run = AnalysisRunRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=snapshot.id,
            catalogue_version_id=catalogue.id,
            engine_version=engine_version,
            workbook_sha256=stored.sha256,
            status="running",
        )
        self.session.add(run)
        self.session.flush()
        return run

    def start_snapshot_run(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        catalogue: RuleCatalogueVersionRecord,
        engine_version: str,
    ) -> AnalysisRunRecord:
        snapshot = self.session.scalar(
            select(DatasetSnapshotRecord).where(
                DatasetSnapshotRecord.organization_id == organization_id,
                DatasetSnapshotRecord.project_id == project_id,
                DatasetSnapshotRecord.id == snapshot_id,
            )
        )
        if snapshot is None:
            raise LookupError(f"Dataset snapshot not found: {snapshot_id}")
        source = self.session.scalar(
            select(SourceFileRecord).where(
                SourceFileRecord.organization_id == organization_id,
                SourceFileRecord.project_id == project_id,
                SourceFileRecord.id == snapshot.source_file_id,
            )
        )
        if source is None:
            raise LookupError(f"Source file metadata not found for snapshot: {snapshot_id}")
        run = AnalysisRunRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=snapshot.id,
            catalogue_version_id=catalogue.id,
            engine_version=engine_version,
            workbook_sha256=source.sha256,
            status="running",
        )
        self.session.add(run)
        self.session.flush()
        return run

    def complete_run(
        self,
        run_id: UUID,
        audit: AuditResult,
        duration_ms: int,
        *,
        executed_rule_ids: list[str] | None = None,
        skipped_rules: list[dict] | None = None,
        raw_row_index: dict[tuple[str, int], int] | None = None,
    ) -> AnalysisRunRecord:
        run = self.session.get(AnalysisRunRecord, run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {run_id}")
        for finding in audit.findings:
            payload = finding.model_dump(mode="json")
            record = FindingRecord(
                analysis_run_id=run.id,
                organization_id=run.organization_id,
                project_id=run.project_id,
                engine_finding_id=finding.finding_id,
                rule_id=finding.rule_id,
                rule_name=finding.rule_name,
                entity_type=finding.entity_type,
                entity_id=finding.entity_id,
                category=finding.category,
                severity=finding.severity,
                status="open",
                title=finding.title,
                description=finding.description,
                metrics=payload["metrics"],
                calculation=payload["calculation"],
                business_impact=finding.business_impact,
                recommendation=finding.recommendation,
                confidence=Decimal(str(finding.confidence)),
            )
            self.session.add(record)
            self.session.flush()
            for order, evidence in enumerate(payload["evidence"]):
                raw_row_ids = []
                if raw_row_index is not None:
                    raw_row_ids = [
                        raw_row_index[(evidence["source_sheet"], row_number)]
                        for row_number in evidence["source_rows"]
                        if (evidence["source_sheet"], row_number) in raw_row_index
                    ]
                self.session.add(FindingEvidenceRecord(
                    finding_id=record.id,
                    evidence_order=order,
                    source_sheet=evidence["source_sheet"],
                    source_rows=evidence["source_rows"],
                    record_ids=evidence["record_ids"],
                    raw_row_ids=raw_row_ids,
                    fields=evidence["fields"],
                    aggregation=evidence.get("aggregation"),
                ))
        run.status = "succeeded"
        run.rule_count = audit.rule_count
        run.finding_count = audit.finding_count
        if executed_rule_ids is not None:
            run.executed_rule_ids = executed_rule_ids
        if skipped_rules is not None:
            run.skipped_rules = skipped_rules
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        self.session.flush()
        return run

    def fail_run(self, run_id: UUID, code: str, message: str, duration_ms: int) -> AnalysisRunRecord:
        run = self.session.get(AnalysisRunRecord, run_id)
        if run is None:
            raise LookupError(f"Analysis run not found: {run_id}")
        run.status = "failed"
        run.safe_error_code = code
        run.safe_error_message = message
        run.duration_ms = duration_ms
        run.completed_at = datetime.now(timezone.utc)
        self.session.flush()
        return run

    def list_runs(self, organization_id: UUID, project_id: UUID) -> list[AnalysisRunRecord]:
        return list(self.session.scalars(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.organization_id == organization_id,
                AnalysisRunRecord.project_id == project_id,
            ).order_by(AnalysisRunRecord.started_at.desc(), AnalysisRunRecord.id.desc())
        ))

    def get_run(self, organization_id: UUID, run_id: UUID) -> AnalysisRunRecord | None:
        return self.session.scalar(select(AnalysisRunRecord).where(
            AnalysisRunRecord.organization_id == organization_id,
            AnalysisRunRecord.id == run_id,
        ))


class FindingRepository:
    VALID_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}

    def __init__(self, session: Session):
        self.session = session

    def list_for_run(
        self, organization_id: UUID, run_id: UUID, *, rule_id: str | None = None,
        severity: str | None = None, category: str | None = None,
        entity_id: str | None = None, status: str | None = None,
    ) -> list[FindingRecord]:
        statement = select(FindingRecord).where(
            FindingRecord.organization_id == organization_id,
            FindingRecord.analysis_run_id == run_id,
        )
        for column, value in (
            (FindingRecord.rule_id, rule_id), (FindingRecord.severity, severity),
            (FindingRecord.category, category), (FindingRecord.entity_id, entity_id),
            (FindingRecord.status, status),
        ):
            if value is not None:
                statement = statement.where(column == value)
        severity_order = case(
            (FindingRecord.severity == "critical", 0),
            (FindingRecord.severity == "warning", 1),
            else_=2,
        )
        return list(self.session.scalars(statement.order_by(
            severity_order, FindingRecord.rule_id, FindingRecord.entity_id
        )))

    def get(self, organization_id: UUID, finding_id: UUID) -> FindingRecord | None:
        return self.session.scalar(select(FindingRecord).where(
            FindingRecord.organization_id == organization_id,
            FindingRecord.id == finding_id,
        ))

    def evidence(self, organization_id: UUID, finding_id: UUID) -> list[FindingEvidenceRecord]:
        return list(self.session.scalars(
            select(FindingEvidenceRecord)
            .join(FindingRecord, FindingRecord.id == FindingEvidenceRecord.finding_id)
            .where(
                FindingRecord.organization_id == organization_id,
                FindingEvidenceRecord.finding_id == finding_id,
            )
            .order_by(FindingEvidenceRecord.evidence_order)
        ))

    def update_status(self, organization_id: UUID, finding_id: UUID, status: str) -> FindingRecord | None:
        finding = self.get(organization_id, finding_id)
        if finding is None:
            return None
        if status not in self.VALID_STATUSES:
            raise ValueError(status)
        finding.status = status
        finding.resolved_at = datetime.now(timezone.utc) if status in {"resolved", "dismissed"} else None
        self.session.add(AuditLogRecord(
            organization_id=organization_id,
            project_id=finding.project_id,
            event_type="finding.status_changed",
            entity_type="finding",
            entity_id=str(finding.id),
            metadata_json={"status": status},
        ))
        self.session.flush()
        return finding
