from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..storage import StoredObject
from .models import (
    DatasetSnapshotRecord,
    GovernedDatasetSnapshotRecord,
    GovernedImportBatchRecord,
    GovernedMappingProfileVersionRecord,
    SourceFileRecord,
)


COMPLETED_SNAPSHOT_STATUSES = ("validated", "validated_with_errors")


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
    )


class SnapshotRepository:
    """Governed writer with read compatibility for homepage snapshots."""

    def __init__(self, session: Session):
        self.session = session

    def resolve_mapping_profile(
        self,
        version: str,
        sha256: str,
        definition: dict,
    ) -> GovernedMappingProfileVersionRecord:
        statement = (
            insert(GovernedMappingProfileVersionRecord)
            .values(version=version, sha256=sha256, definition=definition)
            .on_conflict_do_nothing(index_elements=["version", "sha256"])
            .returning(GovernedMappingProfileVersionRecord)
        )
        record = self.session.scalar(statement)
        if record is None:
            record = self.session.scalar(
                select(GovernedMappingProfileVersionRecord).where(
                    GovernedMappingProfileVersionRecord.version == version,
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

    def complete(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        *,
        status: str,
        row_count_raw: int,
        row_count_canonical: int,
    ) -> GovernedDatasetSnapshotRecord:
        if status not in COMPLETED_SNAPSHOT_STATUSES:
            raise ValueError(f"Unsupported completed snapshot status: {status}")
        if not 0 <= row_count_canonical <= row_count_raw:
            raise ValueError("Canonical row count must be between zero and raw row count")

        snapshot = self._get_ingesting_scoped(
            organization_id, project_id, snapshot_id
        )
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
