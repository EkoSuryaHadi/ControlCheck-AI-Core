from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..ingestion.mapper import IssueSeverity, MappedSnapshot, RowIssue
from ..ingestion.profile import MappingProfileV1
from ..ingestion.types import ExtractedWorkbook, TemplateIssue
from ..models import WBSNode
from ..storage import StoredObject
from .models import (
    CanonicalActualCostRecord,
    CanonicalBudgetRecord,
    CanonicalCommitmentRecord,
    DatasetDomainStatusRecord,
    DatasetSnapshotRecord,
    ImportBatchRecord,
    MappingProfileVersionRecord,
    ProgressRecordRecord,
    RawRowRecord,
    ScheduleActivityRecord,
    SourceFileRecord,
    WBSNodeRecord,
)


COMPLETED_SNAPSHOT_STATUSES = ("validated", "validated_with_errors")
WBS_DEPENDENT_DOMAINS = frozenset(
    {"budget", "actual_cost", "commitments", "schedule", "progress"}
)


class SnapshotImmutableError(RuntimeError):
    pass


def _row_issue_payload(issue: RowIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "field": issue.field,
        "severity": issue.severity.value,
    }


def _template_issue_payload(issue: TemplateIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "domain": issue.domain,
        "sheet_name": issue.sheet_name,
        "severity": IssueSeverity.error.value,
    }


class SnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def resolve_mapping_profile(
        self,
        profile: MappingProfileV1,
        sha256: str,
    ) -> MappingProfileVersionRecord:
        statement = (
            insert(MappingProfileVersionRecord)
            .values(
                version=profile.version,
                sha256=sha256,
                definition=profile.model_dump(mode="json"),
            )
            .on_conflict_do_nothing(index_elements=["version", "sha256"])
            .returning(MappingProfileVersionRecord)
        )
        record = self.session.scalar(statement)
        if record is None:
            record = self.session.scalar(
                select(MappingProfileVersionRecord).where(
                    MappingProfileVersionRecord.version == profile.version,
                    MappingProfileVersionRecord.sha256 == sha256,
                )
            )
        if record is None:
            raise RuntimeError("Mapping profile version could not be resolved")
        return record

    def find_duplicate(
        self,
        organization_id: UUID,
        project_id: UUID,
        dedupe_key: str,
    ) -> DatasetSnapshotRecord | None:
        return self.session.scalar(
            select(DatasetSnapshotRecord).where(
                DatasetSnapshotRecord.organization_id == organization_id,
                DatasetSnapshotRecord.project_id == project_id,
                DatasetSnapshotRecord.dedupe_key == dedupe_key,
                DatasetSnapshotRecord.status.in_(COMPLETED_SNAPSHOT_STATUSES),
            )
        )

    def create_ingesting(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        stored: StoredObject,
        mapping_profile_version_id: UUID,
        dataset_version: str,
        data_date: date,
        source_project_id: str,
        dedupe_key: str | None,
    ) -> DatasetSnapshotRecord:
        source = SourceFileRecord(
            organization_id=organization_id,
            project_id=project_id,
            file_name=filename,
            storage_key=stored.key,
            mime_type=content_type,
            file_size_bytes=stored.size_bytes,
            sha256=stored.sha256,
        )
        self.session.add(source)
        self.session.flush()

        snapshot = DatasetSnapshotRecord(
            organization_id=organization_id,
            project_id=project_id,
            source_file_id=source.id,
            mapping_profile_version_id=mapping_profile_version_id,
            dataset_version=dataset_version,
            data_date=data_date,
            source_project_id=source_project_id,
            dedupe_key=dedupe_key,
            status="ingesting",
        )
        self.session.add(snapshot)
        self.session.flush()

        batch = ImportBatchRecord(
            organization_id=organization_id,
            project_id=project_id,
            dataset_snapshot_id=snapshot.id,
            mapping_profile_version_id=mapping_profile_version_id,
            status="ingesting",
        )
        self.session.add(batch)
        self.session.flush()
        snapshot.import_batch_id = batch.id
        self.session.flush()
        return snapshot

    def _get_ingesting_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> DatasetSnapshotRecord:
        snapshot = self.session.scalar(
            select(DatasetSnapshotRecord).where(
                DatasetSnapshotRecord.organization_id == organization_id,
                DatasetSnapshotRecord.project_id == project_id,
                DatasetSnapshotRecord.id == snapshot_id,
                DatasetSnapshotRecord.status == "ingesting",
            )
        )
        if snapshot is not None:
            return snapshot
        existing = self.get_scoped(organization_id, project_id, snapshot_id)
        if existing is not None:
            raise SnapshotImmutableError(
                f"Dataset snapshot {snapshot_id} is immutable in status {existing.status}"
            )
        raise LookupError(f"Dataset snapshot not found: {snapshot_id}")

    def _get_batch_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot: DatasetSnapshotRecord,
    ) -> ImportBatchRecord:
        batch = self.session.scalar(
            select(ImportBatchRecord).where(
                ImportBatchRecord.organization_id == organization_id,
                ImportBatchRecord.project_id == project_id,
                ImportBatchRecord.dataset_snapshot_id == snapshot.id,
                ImportBatchRecord.id == snapshot.import_batch_id,
            )
        )
        if batch is None:
            raise LookupError(f"Import batch not found for dataset snapshot {snapshot.id}")
        return batch

    def persist_raw_rows(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        extracted: ExtractedWorkbook,
        mapped: MappedSnapshot,
    ) -> dict[tuple[str, int], RawRowRecord]:
        snapshot = self._get_ingesting_scoped(organization_id, project_id, snapshot_id)
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)
        records: dict[tuple[str, int], RawRowRecord] = {}
        for domain, extracted_rows in extracted.rows_by_domain.items():
            mapped_rows = mapped.rows_by_domain.get(domain, [])
            for extracted_row, mapped_row in zip(extracted_rows, mapped_rows, strict=True):
                if mapped_row.record is None:
                    validation_status = "invalid"
                elif mapped_row.issues:
                    validation_status = "warning"
                else:
                    validation_status = "valid"
                raw = RawRowRecord(
                    organization_id=organization_id,
                    project_id=project_id,
                    dataset_snapshot_id=snapshot.id,
                    import_batch_id=batch.id,
                    domain=domain,
                    source_sheet=extracted_row.sheet_name,
                    source_row_number=extracted_row.source_row_number,
                    row_hash=extracted_row.source_key,
                    raw_data=extracted_row.values,
                    validation_status=validation_status,
                    validation_errors=[_row_issue_payload(issue) for issue in mapped_row.issues],
                )
                self.session.add(raw)
                records[(domain, extracted_row.source_row_number)] = raw
        self.session.flush()
        return records

    def persist_canonical_rows(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        mapped: MappedSnapshot,
        raw_rows: dict[tuple[str, int], RawRowRecord],
    ) -> None:
        """Persist each valid source row using source identity, not business-ID uniqueness.

        Repeated transaction, budget, activity, and other business identifiers remain
        canonical so data-quality rules can inspect them. ``source_key`` plus exact
        ``raw_row_id`` lineage is the persistence identity within a snapshot.
        """
        snapshot = self._get_ingesting_scoped(organization_id, project_id, snapshot_id)
        wbs_by_code: dict[str, WBSNodeRecord] = {}
        wbs_pairs: list[tuple[WBSNodeRecord, WBSNode]] = []
        for result in mapped.rows_by_domain.get("wbs", []):
            if not isinstance(result.record, WBSNode):
                continue
            record = result.record
            raw = raw_rows[("wbs", record.source.row_number)]
            node = WBSNodeRecord(
                organization_id=organization_id,
                project_id=project_id,
                dataset_snapshot_id=snapshot.id,
                raw_row_id=raw.id,
                parent_id=None,
                source_key=result.source_key,
                wbs_code=record.wbs_code,
                wbs_name=record.wbs_name,
                parent_wbs=record.parent_wbs,
                discipline=record.discipline,
                level=record.level,
            )
            self.session.add(node)
            wbs_by_code[record.wbs_code] = node
            wbs_pairs.append((node, record))
        self.session.flush()
        for node, record in wbs_pairs:
            if record.parent_wbs is not None:
                node.parent_id = wbs_by_code[record.parent_wbs].id
        self.session.flush()

        fact_models = {
            "budget": CanonicalBudgetRecord,
            "actual_cost": CanonicalActualCostRecord,
            "commitments": CanonicalCommitmentRecord,
            "schedule": ScheduleActivityRecord,
            "progress": ProgressRecordRecord,
        }
        for domain, model in fact_models.items():
            for result in mapped.rows_by_domain.get(domain, []):
                record = result.record
                if record is None:
                    continue
                raw = raw_rows[(domain, record.source.row_number)]
                payload = record.model_dump(exclude={"source"})
                wbs_code = payload.get("wbs_code")
                wbs_node = wbs_by_code.get(wbs_code) if wbs_code is not None else None
                self.session.add(
                    model(
                        organization_id=organization_id,
                        project_id=project_id,
                        dataset_snapshot_id=snapshot.id,
                        raw_row_id=raw.id,
                        wbs_node_id=wbs_node.id if wbs_node is not None else None,
                        source_key=result.source_key,
                        **payload,
                    )
                )
        self.session.flush()

    def complete(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        extracted: ExtractedWorkbook,
        mapped: MappedSnapshot,
    ) -> DatasetSnapshotRecord:
        snapshot = self._get_ingesting_scoped(organization_id, project_id, snapshot_id)
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)

        rows_read = 0
        rows_valid = 0
        rows_warning = 0
        rows_rejected = 0
        rows_canonical = 0
        template_by_domain: dict[str, list[TemplateIssue]] = {
            domain: [] for domain in mapped.rows_by_domain
        }
        for issue in extracted.template_errors:
            template_by_domain.setdefault(issue.domain, []).append(issue)

        for domain, rows in mapped.rows_by_domain.items():
            domain_valid = sum(row.record is not None and not row.issues for row in rows)
            domain_warning = sum(row.record is not None and bool(row.issues) for row in rows)
            domain_rejected = sum(row.record is None for row in rows)
            domain_canonical = domain_valid + domain_warning
            row_errors = [
                issue
                for row in rows
                for issue in row.issues
                if issue.severity is IssueSeverity.error
            ]
            row_warnings = [
                issue
                for row in rows
                for issue in row.issues
                if issue.severity is IssueSeverity.warning
            ]
            domain_issues = mapped.domain_issues.get(domain, ())
            dependency_issues: list[dict[str, Any]] = []
            if (
                domain in WBS_DEPENDENT_DOMAINS
                and mapped.domain_statuses["wbs"].value == "blocked"
            ):
                dependency_issues.append(
                    {
                        "code": "blocked_by_wbs",
                        "message": "Domain is blocked because the WBS domain is blocked",
                        "dependency_domain": "wbs",
                        "severity": IssueSeverity.error.value,
                    }
                )
            error_count = len(template_by_domain.get(domain, [])) + len(row_errors) + sum(
                issue.severity is IssueSeverity.error for issue in domain_issues
            ) + len(dependency_issues)
            warning_count = len(row_warnings) + sum(
                issue.severity is IssueSeverity.warning for issue in domain_issues
            )
            self.session.add(
                DatasetDomainStatusRecord(
                    organization_id=organization_id,
                    project_id=project_id,
                    dataset_snapshot_id=snapshot.id,
                    domain=domain,
                    status=mapped.domain_statuses[domain].value,
                    row_count_raw=len(rows),
                    row_count_canonical=domain_canonical,
                    error_count=error_count,
                    warning_count=warning_count,
                    validation_summary={
                        "template_errors": [
                            _template_issue_payload(issue)
                            for issue in template_by_domain.get(domain, [])
                        ],
                        "domain_issues": [_row_issue_payload(issue) for issue in domain_issues],
                        "dependency_issues": dependency_issues,
                    },
                )
            )
            rows_read += len(rows)
            rows_valid += domain_valid
            rows_warning += domain_warning
            rows_rejected += domain_rejected
            rows_canonical += domain_canonical

        batch.status = "completed"
        batch.rows_read = rows_read
        batch.rows_valid = rows_valid
        batch.rows_warning = rows_warning
        batch.rows_rejected = rows_rejected
        batch.error_summary = {
            "error_count": mapped.error_count,
            "warning_count": mapped.warning_count,
            "project_issues": [_row_issue_payload(issue) for issue in mapped.project_issues],
        }
        batch.completed_at = datetime.now(timezone.utc)
        snapshot.row_count_raw = rows_read
        snapshot.row_count_canonical = rows_canonical
        snapshot.status = "validated_with_errors" if mapped.error_count else "validated"
        self.session.flush()
        return snapshot

    def fail(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        code: str,
        message: str,
        error_summary: dict[str, Any] | None = None,
    ) -> DatasetSnapshotRecord:
        snapshot = self._get_ingesting_scoped(organization_id, project_id, snapshot_id)
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)
        for model in (
            CanonicalBudgetRecord,
            CanonicalActualCostRecord,
            CanonicalCommitmentRecord,
            ScheduleActivityRecord,
            ProgressRecordRecord,
        ):
            self.session.execute(
                delete(model).where(
                    model.organization_id == organization_id,
                    model.project_id == project_id,
                    model.dataset_snapshot_id == snapshot.id,
                )
            )
        self.session.execute(
            delete(WBSNodeRecord).where(
                WBSNodeRecord.organization_id == organization_id,
                WBSNodeRecord.project_id == project_id,
                WBSNodeRecord.dataset_snapshot_id == snapshot.id,
            )
        )
        self.session.execute(
            delete(DatasetDomainStatusRecord).where(
                DatasetDomainStatusRecord.organization_id == organization_id,
                DatasetDomainStatusRecord.project_id == project_id,
                DatasetDomainStatusRecord.dataset_snapshot_id == snapshot.id,
            )
        )
        self.session.execute(
            delete(RawRowRecord).where(
                RawRowRecord.organization_id == organization_id,
                RawRowRecord.project_id == project_id,
                RawRowRecord.dataset_snapshot_id == snapshot.id,
            )
        )
        batch.status = "failed"
        batch.rows_read = 0
        batch.rows_valid = 0
        batch.rows_warning = 0
        batch.rows_rejected = 0
        batch.safe_error_code = code
        batch.safe_error_message = message
        batch.error_summary = error_summary
        batch.completed_at = datetime.now(timezone.utc)
        snapshot.dedupe_key = None
        snapshot.row_count_raw = 0
        snapshot.row_count_canonical = 0
        snapshot.status = "failed"
        self.session.flush()
        return snapshot

    def list_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
    ) -> list[DatasetSnapshotRecord]:
        return list(
            self.session.scalars(
                select(DatasetSnapshotRecord)
                .where(
                    DatasetSnapshotRecord.organization_id == organization_id,
                    DatasetSnapshotRecord.project_id == project_id,
                )
                .order_by(DatasetSnapshotRecord.created_at.desc(), DatasetSnapshotRecord.id.desc())
            )
        )

    def get_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> DatasetSnapshotRecord | None:
        return self.session.scalar(
            select(DatasetSnapshotRecord).where(
                DatasetSnapshotRecord.organization_id == organization_id,
                DatasetSnapshotRecord.project_id == project_id,
                DatasetSnapshotRecord.id == snapshot_id,
            )
        )


__all__ = ["SnapshotImmutableError", "SnapshotRepository"]
