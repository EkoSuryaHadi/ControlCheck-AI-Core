from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session


from .models import (
    AIConversationRecord,
    AIMessageRecord,
    AnalysisRunRecord,
    AuditLogRecord,
    BudgetRecordRecord,
    CommitmentRecordRecord,
    CostRecordRecord,
    DatasetSnapshotRecord,
    FindingEvidenceRecord,
    FindingRecord,
    HealthSnapshotRecord,
    ImportBatchRecord,
    ImportColumnMappingRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    ProgressRecordRecord,
    ProjectMemberRecord,
    ProjectRecord,
    RawRowRecord,
    RuleCatalogueVersionRecord,
    ScheduleActivityRecord,
    SourceFileRecord,
    UserRecord,
    WBSNodeRecord,
)


from ..ingestion.normalizer import CanonicalFactBundle
from ..ingestion.raw_store import RawRowItem
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

    def list_for_organization(
        self, organization_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[ProjectRecord], int]:
        total = self.session.scalar(
            select(func.count(ProjectRecord.id)).where(ProjectRecord.organization_id == organization_id)
        ) or 0
        items = list(
            self.session.scalars(
                select(ProjectRecord)
                .where(ProjectRecord.organization_id == organization_id)
                .order_by(ProjectRecord.created_at, ProjectRecord.id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

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
        raw_items: list[RawRowItem] | None = None,
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

        if raw_items:
            raw_row_map = RawRowRepository(self.session).persist_raw_rows(
                organization_id, project_id, source.id, raw_items
            )
            from ..ingestion.normalizer import normalize_dataset_facts
            bundle = normalize_dataset_facts(
                organization_id, project_id, snapshot.id, dataset, raw_row_map
            )
            CanonicalFactRepository(self.session).persist_bundle(bundle)
            batch = ImportBatchRecord(
                organization_id=organization_id,
                project_id=project_id,
                source_file_id=source.id,
                dataset_snapshot_id=snapshot.id,
                status="completed",
                row_count=len(raw_items),
            )
            self.session.add(batch)
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


    def complete_run(self, run_id: UUID, audit: AuditResult, duration_ms: int) -> AnalysisRunRecord:
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
                self.session.add(FindingEvidenceRecord(
                    finding_id=record.id,
                    evidence_order=order,
                    source_sheet=evidence["source_sheet"],
                    source_rows=evidence["source_rows"],
                    record_ids=evidence["record_ids"],
                    fields=evidence["fields"],
                    aggregation=evidence.get("aggregation"),
                ))
        run.status = "succeeded"
        run.rule_count = audit.rule_count
        run.finding_count = audit.finding_count
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

    def list_runs(
        self, organization_id: UUID, project_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[AnalysisRunRecord], int]:
        total = self.session.scalar(
            select(func.count(AnalysisRunRecord.id)).where(
                AnalysisRunRecord.organization_id == organization_id,
                AnalysisRunRecord.project_id == project_id,
            )
        ) or 0
        items = list(self.session.scalars(
            select(AnalysisRunRecord).where(
                AnalysisRunRecord.organization_id == organization_id,
                AnalysisRunRecord.project_id == project_id,
            ).order_by(AnalysisRunRecord.started_at.desc(), AnalysisRunRecord.id.desc())
            .limit(limit)
            .offset(offset)
        ))
        return items, total

    def get_run(self, organization_id: UUID, run_id: UUID) -> AnalysisRunRecord | None:
        return self.session.scalar(select(AnalysisRunRecord).where(
            AnalysisRunRecord.organization_id == organization_id,
            AnalysisRunRecord.id == run_id,
        ))

    def get_run_by_idempotency_key(
        self, organization_id: UUID, project_id: UUID, idempotency_key: str
    ) -> AnalysisRunRecord | None:
        log = self.session.scalar(
            select(AuditLogRecord).where(
                AuditLogRecord.organization_id == organization_id,
                AuditLogRecord.project_id == project_id,
                AuditLogRecord.event_type == "analysis_run.created",
                AuditLogRecord.metadata_json["idempotency_key"].astext == idempotency_key,
            )
        )
        if log and log.entity_id:
            try:
                run_id = UUID(log.entity_id)
                return self.get_run(organization_id, run_id)
            except ValueError:
                return None
        return None

    def record_idempotency(
        self, organization_id: UUID, project_id: UUID, run_id: UUID, idempotency_key: str
    ) -> None:
        self.session.add(AuditLogRecord(
            organization_id=organization_id,
            project_id=project_id,
            event_type="analysis_run.created",
            entity_type="analysis_run",
            entity_id=str(run_id),
            metadata_json={"idempotency_key": idempotency_key},
        ))
        self.session.flush()


class FindingRepository:
    VALID_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}

    def __init__(self, session: Session):
        self.session = session

    def list_for_run(
        self, organization_id: UUID, run_id: UUID, *, rule_id: str | None = None,
        severity: str | None = None, category: str | None = None,
        entity_id: str | None = None, status: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[FindingRecord], int]:
        base_statement = select(FindingRecord).where(
            FindingRecord.organization_id == organization_id,
            FindingRecord.analysis_run_id == run_id,
        )
        count_statement = select(func.count(FindingRecord.id)).where(
            FindingRecord.organization_id == organization_id,
            FindingRecord.analysis_run_id == run_id,
        )
        for column, value in (
            (FindingRecord.rule_id, rule_id), (FindingRecord.severity, severity),
            (FindingRecord.category, category), (FindingRecord.entity_id, entity_id),
            (FindingRecord.status, status),
        ):
            if value is not None:
                base_statement = base_statement.where(column == value)
                count_statement = count_statement.where(column == value)

        total = self.session.scalar(count_statement) or 0

        severity_order = case(
            (FindingRecord.severity == "critical", 0),
            (FindingRecord.severity == "warning", 1),
            else_=2,
        )
        items = list(self.session.scalars(
            base_statement.order_by(
                severity_order, FindingRecord.rule_id, FindingRecord.entity_id
            )
            .limit(limit)
            .offset(offset)
        ))
        return items, total


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


class RawRowRepository:
    def __init__(self, session: Session):
        self.session = session

    def persist_raw_rows(
        self,
        organization_id: UUID,
        project_id: UUID,
        source_file_id: UUID,
        raw_items: list[RawRowItem],
    ) -> dict[tuple[str, int], UUID]:
        """Bulk inserts raw rows and returns a lookup map of (sheet_name, row_number) -> row_uuid."""
        records = [
            RawRowRecord(
                id=item.id,
                organization_id=organization_id,
                project_id=project_id,
                source_file_id=source_file_id,
                sheet_name=item.sheet_name,
                row_number=item.row_number,
                raw_data=item.raw_data,
            )
            for item in raw_items
        ]
        self.session.add_all(records)
        self.session.flush()
        return {(r.sheet_name, r.row_number): r.id for r in records}

    def list_for_file(
        self,
        organization_id: UUID,
        source_file_id: UUID,
        sheet_name: str | None = None,
    ) -> list[RawRowRecord]:
        stmt = select(RawRowRecord).where(
            RawRowRecord.organization_id == organization_id,
            RawRowRecord.source_file_id == source_file_id,
        )
        if sheet_name:
            stmt = stmt.where(RawRowRecord.sheet_name == sheet_name)
        return list(self.session.scalars(stmt.order_by(RawRowRecord.sheet_name, RawRowRecord.row_number)))


class CanonicalFactRepository:
    def __init__(self, session: Session):
        self.session = session

    def persist_bundle(self, bundle: CanonicalFactBundle) -> None:
        """Persists all canonical fact records in the bundle."""
        self.session.add_all(bundle.wbs_nodes)
        self.session.add_all(bundle.budgets)
        self.session.add_all(bundle.costs)
        self.session.add_all(bundle.commitments)
        self.session.add_all(bundle.schedules)
        self.session.add_all(bundle.progress)
        self.session.flush()

    def get_wbs_nodes(self, organization_id: UUID, dataset_snapshot_id: UUID) -> list[WBSNodeRecord]:
        return list(self.session.scalars(
            select(WBSNodeRecord).where(
                WBSNodeRecord.organization_id == organization_id,
                WBSNodeRecord.dataset_snapshot_id == dataset_snapshot_id,
            ).order_by(WBSNodeRecord.wbs_code)
        ))

    def get_budgets(self, organization_id: UUID, dataset_snapshot_id: UUID) -> list[BudgetRecordRecord]:
        return list(self.session.scalars(
            select(BudgetRecordRecord).where(
                BudgetRecordRecord.organization_id == organization_id,
                BudgetRecordRecord.dataset_snapshot_id == dataset_snapshot_id,
            ).order_by(BudgetRecordRecord.budget_id)
        ))

    def get_costs(self, organization_id: UUID, dataset_snapshot_id: UUID) -> list[CostRecordRecord]:
        return list(self.session.scalars(
            select(CostRecordRecord).where(
                CostRecordRecord.organization_id == organization_id,
                CostRecordRecord.dataset_snapshot_id == dataset_snapshot_id,
            ).order_by(CostRecordRecord.transaction_date, CostRecordRecord.transaction_id)
        ))


class HealthRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_snapshot(
        self,
        organization_id: UUID,
        project_id: UUID,
        analysis_run_id: UUID,
        overall_score: float,
        cost_score: float,
        schedule_score: float,
        progress_score: float,
        dq_score: float,
        score_band: str,
        component_breakdown: dict,
        key_drivers: list,
        score_version: str = "1.0",
    ) -> HealthSnapshotRecord:
        record = HealthSnapshotRecord(
            organization_id=organization_id,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            overall_score=overall_score,
            cost_score=cost_score,
            schedule_score=schedule_score,
            progress_score=progress_score,
            dq_score=dq_score,
            score_band=score_band,
            component_breakdown=component_breakdown,
            key_drivers=key_drivers,
            score_version=score_version,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_by_run(
        self, organization_id: UUID, analysis_run_id: UUID
    ) -> HealthSnapshotRecord | None:
        return self.session.scalar(
            select(HealthSnapshotRecord).where(
                HealthSnapshotRecord.organization_id == organization_id,
                HealthSnapshotRecord.analysis_run_id == analysis_run_id,
            )
        )

    def list_trends(
        self, organization_id: UUID, project_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[HealthSnapshotRecord], int]:
        total = self.session.scalar(
            select(func.count(HealthSnapshotRecord.id)).where(
                HealthSnapshotRecord.organization_id == organization_id,
                HealthSnapshotRecord.project_id == project_id,
            )
        ) or 0
        items = list(self.session.scalars(
            select(HealthSnapshotRecord).where(
                HealthSnapshotRecord.organization_id == organization_id,
                HealthSnapshotRecord.project_id == project_id,
            )
            .order_by(HealthSnapshotRecord.created_at.desc(), HealthSnapshotRecord.id.desc())
            .limit(limit)
            .offset(offset)
        ))
        return items, total


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_user(
        self, email: str, password_hash: str, full_name: str | None = None
    ) -> UserRecord:
        user = UserRecord(
            email=email.strip().lower(),
            password_hash=password_hash,
            full_name=full_name.strip() if full_name else None,
            status="active",
        )
        self.session.add(user)
        self.session.flush()
        return user

    def get_by_email(self, email: str) -> UserRecord | None:
        return self.session.scalar(
            select(UserRecord).where(UserRecord.email == email.strip().lower())
        )

    def get_by_id(self, user_id: UUID) -> UserRecord | None:
        return self.session.scalar(
            select(UserRecord).where(UserRecord.id == user_id)
        )

    def add_org_member(
        self, organization_id: UUID, user_id: UUID, role: str = "org_member"
    ) -> OrganizationMemberRecord:
        member = OrganizationMemberRecord(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        self.session.flush()
        return member

    def get_org_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMemberRecord | None:
        return self.session.scalar(
            select(OrganizationMemberRecord).where(
                OrganizationMemberRecord.organization_id == organization_id,
                OrganizationMemberRecord.user_id == user_id,
            )
        )

    def add_project_member(
        self, project_id: UUID, user_id: UUID, role: str = "project_viewer"
    ) -> ProjectMemberRecord:
        member = ProjectMemberRecord(
            project_id=project_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        self.session.flush()
        return member

    def get_project_membership(
        self, project_id: UUID, user_id: UUID
    ) -> ProjectMemberRecord | None:
        return self.session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == project_id,
                ProjectMemberRecord.user_id == user_id,
            )
        )


class AIRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_conversation(
        self,
        organization_id: UUID,
        project_id: UUID,
        user_id: UUID | None = None,
        title: str = "Project Audit Conversation",
    ) -> AIConversationRecord:
        conv = AIConversationRecord(
            organization_id=organization_id,
            project_id=project_id,
            user_id=user_id,
            title=title,
        )
        self.session.add(conv)
        self.session.flush()
        return conv

    def get_conversation(
        self, organization_id: UUID, conversation_id: UUID
    ) -> AIConversationRecord | None:
        return self.session.scalar(
            select(AIConversationRecord).where(
                AIConversationRecord.organization_id == organization_id,
                AIConversationRecord.id == conversation_id,
            )
        )

    def list_conversations(
        self, organization_id: UUID, project_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[AIConversationRecord], int]:
        total = self.session.scalar(
            select(func.count(AIConversationRecord.id)).where(
                AIConversationRecord.organization_id == organization_id,
                AIConversationRecord.project_id == project_id,
            )
        ) or 0
        items = list(self.session.scalars(
            select(AIConversationRecord).where(
                AIConversationRecord.organization_id == organization_id,
                AIConversationRecord.project_id == project_id,
            )
            .order_by(AIConversationRecord.created_at.desc(), AIConversationRecord.id.desc())
            .limit(limit)
            .offset(offset)
        ))
        return items, total

    def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        tool_calls: dict | list | None = None,
        model_version: str = "deterministic-grounded-v1",
    ) -> AIMessageRecord:
        msg = AIMessageRecord(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            model_version=model_version,
        )
        self.session.add(msg)
        self.session.flush()
        return msg

    def list_messages(self, conversation_id: UUID) -> list[AIMessageRecord]:
        return list(self.session.scalars(
            select(AIMessageRecord).where(
                AIMessageRecord.conversation_id == conversation_id
            ).order_by(AIMessageRecord.created_at.asc(), AIMessageRecord.id.asc())
        ))




