from __future__ import annotations

from dataclasses import dataclass
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
    DatasetSnapshotRecord,
    GovernedActualCostRecord,
    GovernedBudgetRecord,
    GovernedCommitmentRecord,
    GovernedDatasetSnapshotRecord,
    GovernedDatasetDomainStatusRecord,
    GovernedImportBatchRecord,
    GovernedMappingProfileVersionRecord,
    GovernedProgressRecord,
    GovernedRawRowRecord,
    GovernedScheduleActivityRecord,
    GovernedWBSNodeRecord,
    SourceFileRecord,
)


COMPLETED_SNAPSHOT_STATUSES = ("validated", "validated_with_errors")
WBS_DEPENDENT_DOMAINS = frozenset(
    {"budget", "actual_cost", "commitments", "schedule", "progress"}
)


class SnapshotImmutableError(RuntimeError):
    """Raised when a caller attempts to mutate a completed snapshot."""


@dataclass(frozen=True)
class SnapshotView:
    id: UUID
    organization_id: UUID
    project_id: UUID
    source_file_id: UUID
    dataset_version: str
    data_date: date
    source_project_id: str
    source_project_name: str | None
    status: str
    row_count_raw: int | None
    row_count_canonical: int | None
    created_at: datetime
    storage_contract: str
    mapping_profile_version_id: UUID | None
    dedupe_key: str | None


def _governed_view(record: GovernedDatasetSnapshotRecord) -> SnapshotView:
    return SnapshotView(
        id=record.id,
        organization_id=record.organization_id,
        project_id=record.project_id,
        source_file_id=record.source_file_id,
        dataset_version=record.dataset_version,
        data_date=record.data_date,
        source_project_id=record.source_project_id,
        source_project_name=record.source_project_name,
        status=record.status,
        row_count_raw=record.row_count_raw,
        row_count_canonical=record.row_count_canonical,
        created_at=record.created_at,
        storage_contract="governed",
        mapping_profile_version_id=record.mapping_profile_version_id,
        dedupe_key=record.dedupe_key,
    )


def _simplified_view(record: DatasetSnapshotRecord) -> SnapshotView:
    return SnapshotView(
        id=record.id,
        organization_id=record.organization_id,
        project_id=record.project_id,
        source_file_id=record.source_file_id,
        dataset_version=record.dataset_version,
        data_date=record.data_date,
        source_project_id=record.source_project_id,
        source_project_name=None,
        status=record.status,
        row_count_raw=None,
        row_count_canonical=None,
        created_at=record.created_at,
        storage_contract="simplified",
        mapping_profile_version_id=None,
        dedupe_key=None,
    )


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
    """Governed writer with read compatibility for homepage snapshots."""

    def __init__(self, session: Session):
        self.session = session

    def resolve_mapping_profile(
        self,
        version: MappingProfileV1 | str,
        sha256: str,
        definition: dict | None = None,
    ) -> GovernedMappingProfileVersionRecord:
        if isinstance(version, MappingProfileV1):
            profile = version
            resolved_version = profile.version
            resolved_definition = profile.model_dump(mode="json")
        else:
            resolved_version = version
            if definition is None:
                raise ValueError("Mapping profile definition is required")
            resolved_definition = definition
        statement = (
            insert(GovernedMappingProfileVersionRecord)
            .values(
                version=resolved_version,
                sha256=sha256,
                definition=resolved_definition,
            )
            .on_conflict_do_nothing(index_elements=["version", "sha256"])
            .returning(GovernedMappingProfileVersionRecord)
        )
        record = self.session.scalar(statement)
        if record is None:
            record = self.session.scalar(
                select(GovernedMappingProfileVersionRecord).where(
                    GovernedMappingProfileVersionRecord.version
                    == resolved_version,
                    GovernedMappingProfileVersionRecord.sha256 == sha256,
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
    ) -> GovernedDatasetSnapshotRecord | None:
        return self.session.scalar(
            select(GovernedDatasetSnapshotRecord).where(
                GovernedDatasetSnapshotRecord.organization_id == organization_id,
                GovernedDatasetSnapshotRecord.project_id == project_id,
                GovernedDatasetSnapshotRecord.dedupe_key == dedupe_key,
                GovernedDatasetSnapshotRecord.status.in_(
                    COMPLETED_SNAPSHOT_STATUSES
                ),
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
        source_project_name: str,
        dedupe_key: str | None,
    ) -> GovernedDatasetSnapshotRecord:
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

        snapshot = GovernedDatasetSnapshotRecord(
            organization_id=organization_id,
            project_id=project_id,
            source_file_id=source.id,
            mapping_profile_version_id=mapping_profile_version_id,
            dataset_version=dataset_version,
            data_date=data_date,
            source_project_id=source_project_id,
            source_project_name=source_project_name,
            dedupe_key=dedupe_key,
            status="ingesting",
        )
        self.session.add(snapshot)
        self.session.flush()

        batch = GovernedImportBatchRecord(
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

    def _get_governed_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> GovernedDatasetSnapshotRecord | None:
        return self.session.scalar(
            select(GovernedDatasetSnapshotRecord).where(
                GovernedDatasetSnapshotRecord.organization_id == organization_id,
                GovernedDatasetSnapshotRecord.project_id == project_id,
                GovernedDatasetSnapshotRecord.id == snapshot_id,
            )
        )

    def _get_ingesting_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> GovernedDatasetSnapshotRecord:
        snapshot = self._get_governed_scoped(
            organization_id, project_id, snapshot_id
        )
        if snapshot is None:
            raise LookupError(f"Governed dataset snapshot not found: {snapshot_id}")
        if snapshot.status != "ingesting":
            raise SnapshotImmutableError(
                f"Dataset snapshot {snapshot_id} is immutable in status {snapshot.status}"
            )
        return snapshot

    def _get_batch_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot: GovernedDatasetSnapshotRecord,
    ) -> GovernedImportBatchRecord:
        batch = self.session.scalar(
            select(GovernedImportBatchRecord).where(
                GovernedImportBatchRecord.organization_id == organization_id,
                GovernedImportBatchRecord.project_id == project_id,
                GovernedImportBatchRecord.dataset_snapshot_id == snapshot.id,
                GovernedImportBatchRecord.id == snapshot.import_batch_id,
            )
        )
        if batch is None:
            raise LookupError(
                f"Import batch not found for governed dataset snapshot {snapshot.id}"
            )
        return batch

    def persist_raw_rows(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        extracted: ExtractedWorkbook,
        mapped: MappedSnapshot,
    ) -> dict[tuple[str, int], GovernedRawRowRecord]:
        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)
        records: dict[tuple[str, int], GovernedRawRowRecord] = {}
        for domain, extracted_rows in extracted.rows_by_domain.items():
            mapped_rows = mapped.rows_by_domain.get(domain, [])
            for extracted_row, mapped_row in zip(
                extracted_rows, mapped_rows, strict=True
            ):
                if mapped_row.record is None:
                    validation_status = "invalid"
                elif mapped_row.issues:
                    validation_status = "warning"
                else:
                    validation_status = "valid"
                raw = GovernedRawRowRecord(
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
                    validation_errors=[
                        _row_issue_payload(issue) for issue in mapped_row.issues
                    ],
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
        raw_rows: dict[tuple[str, int], GovernedRawRowRecord],
    ) -> None:
        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
        wbs_by_code: dict[str, GovernedWBSNodeRecord] = {}
        wbs_pairs: list[tuple[GovernedWBSNodeRecord, WBSNode]] = []
        for result in mapped.rows_by_domain.get("wbs", []):
            if not isinstance(result.record, WBSNode):
                continue
            record = result.record
            raw = raw_rows[("wbs", record.source.row_number)]
            node = GovernedWBSNodeRecord(
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
            "budget": GovernedBudgetRecord,
            "actual_cost": GovernedActualCostRecord,
            "commitments": GovernedCommitmentRecord,
            "schedule": GovernedScheduleActivityRecord,
            "progress": GovernedProgressRecord,
        }
        for domain, model in fact_models.items():
            for result in mapped.rows_by_domain.get(domain, []):
                record = result.record
                if record is None:
                    continue
                raw = raw_rows[(domain, record.source.row_number)]
                payload = record.model_dump(exclude={"source"})
                wbs_code = payload.get("wbs_code")
                wbs_node = (
                    wbs_by_code.get(wbs_code) if wbs_code is not None else None
                )
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
        extracted: ExtractedWorkbook | None = None,
        mapped: MappedSnapshot | None = None,
        *,
        status: str | None = None,
        row_count_raw: int | None = None,
        row_count_canonical: int | None = None,
    ) -> GovernedDatasetSnapshotRecord:
        if extracted is not None or mapped is not None:
            if extracted is None or mapped is None:
                raise ValueError("Extracted and mapped snapshots are both required")
            return self._complete_mapped(
                organization_id, project_id, snapshot_id, extracted, mapped
            )
        if status is None or row_count_raw is None or row_count_canonical is None:
            raise ValueError("Snapshot status and row counts are required")
        if status not in COMPLETED_SNAPSHOT_STATUSES:
            raise ValueError(f"Unsupported completed snapshot status: {status}")
        if not 0 <= row_count_canonical <= row_count_raw:
            raise ValueError("Canonical row count must be between zero and raw row count")

        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)

        batch.status = "completed"
        batch.rows_read = row_count_raw
        batch.rows_valid = row_count_canonical
        batch.rows_rejected = row_count_raw - row_count_canonical
        batch.completed_at = datetime.now(timezone.utc)
        snapshot.row_count_raw = row_count_raw
        snapshot.row_count_canonical = row_count_canonical
        snapshot.status = status
        self.session.flush()
        return snapshot

    def _complete_mapped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        extracted: ExtractedWorkbook,
        mapped: MappedSnapshot,
    ) -> GovernedDatasetSnapshotRecord:
        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)
        rows_read = rows_valid = rows_warning = rows_rejected = rows_canonical = 0
        template_by_domain: dict[str, list[TemplateIssue]] = {
            domain: [] for domain in mapped.rows_by_domain
        }
        for issue in extracted.template_errors:
            template_by_domain.setdefault(issue.domain, []).append(issue)
        for domain, rows in mapped.rows_by_domain.items():
            domain_valid = sum(row.record is not None and not row.issues for row in rows)
            domain_warning = sum(
                row.record is not None and bool(row.issues) for row in rows
            )
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
            error_count = (
                len(template_by_domain.get(domain, []))
                + len(row_errors)
                + sum(
                    issue.severity is IssueSeverity.error
                    for issue in domain_issues
                )
                + len(dependency_issues)
            )
            warning_count = len(row_warnings) + sum(
                issue.severity is IssueSeverity.warning
                for issue in domain_issues
            )
            self.session.add(
                GovernedDatasetDomainStatusRecord(
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
                        "domain_issues": [
                            _row_issue_payload(issue) for issue in domain_issues
                        ],
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
            "project_issues": [
                _row_issue_payload(issue) for issue in mapped.project_issues
            ],
        }
        batch.completed_at = datetime.now(timezone.utc)
        snapshot.row_count_raw = rows_read
        snapshot.row_count_canonical = rows_canonical
        snapshot.status = (
            "validated_with_errors" if mapped.error_count else "validated"
        )
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
    ) -> GovernedDatasetSnapshotRecord:
        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
        batch = self._get_batch_scoped(organization_id, project_id, snapshot)
        for model in (
            GovernedBudgetRecord,
            GovernedActualCostRecord,
            GovernedCommitmentRecord,
            GovernedScheduleActivityRecord,
            GovernedProgressRecord,
            GovernedWBSNodeRecord,
            GovernedDatasetDomainStatusRecord,
            GovernedRawRowRecord,
        ):
            self.session.execute(
                delete(model).where(
                    model.organization_id == organization_id,
                    model.project_id == project_id,
                    model.dataset_snapshot_id == snapshot.id,
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
    ) -> list[SnapshotView]:
        governed = list(
            self.session.scalars(
                select(GovernedDatasetSnapshotRecord).where(
                    GovernedDatasetSnapshotRecord.organization_id == organization_id,
                    GovernedDatasetSnapshotRecord.project_id == project_id,
                )
            )
        )
        simplified = list(
            self.session.scalars(
                select(DatasetSnapshotRecord).where(
                    DatasetSnapshotRecord.organization_id == organization_id,
                    DatasetSnapshotRecord.project_id == project_id,
                )
            )
        )
        by_id = {record.id: _simplified_view(record) for record in simplified}
        by_id.update({record.id: _governed_view(record) for record in governed})
        return sorted(
            by_id.values(),
            key=lambda item: (item.created_at, item.id),
            reverse=True,
        )

    def get_scoped(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ) -> SnapshotView | None:
        governed = self._get_governed_scoped(
            organization_id, project_id, snapshot_id
        )
        if governed is not None:
            return _governed_view(governed)
        simplified = self.session.scalar(
            select(DatasetSnapshotRecord).where(
                DatasetSnapshotRecord.organization_id == organization_id,
                DatasetSnapshotRecord.project_id == project_id,
                DatasetSnapshotRecord.id == snapshot_id,
            )
        )
        return _simplified_view(simplified) if simplified is not None else None


__all__ = [
    "COMPLETED_SNAPSHOT_STATUSES",
    "SnapshotImmutableError",
    "SnapshotRepository",
    "SnapshotView",
]
