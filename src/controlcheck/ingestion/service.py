from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..errors import ControlCheckApplicationError
from ..persistence.ingestion_repositories import SnapshotRepository
from ..persistence.models import GovernedDatasetSnapshotRecord, SourceFileRecord
from ..persistence.repositories import ProjectRepository
from ..storage import FileStorage
from .extractor import extract_workbook
from .mapper import IssueSeverity, RowIssue, map_extracted_workbook
from .mpp_converter import MppConversionError
from .profile import MappingProfileV1, mapping_profile_sha256


DEDUPE_INDEX_NAME = "ux_governed_snapshots_dedupe_key_not_null"


@dataclass(frozen=True)
class SnapshotIngestionResult:
    snapshot: GovernedDatasetSnapshotRecord
    outcome: Literal["created", "deduplicated"]

    def __getattr__(self, name: str):
        """Preserve the pre-result snapshot attribute interface for callers."""
        return getattr(self.snapshot, name)


def _dedupe_key(
    organization_id: UUID,
    project_id: UUID,
    workbook_sha256: str,
    profile_sha256: str,
) -> str:
    payload = json.dumps(
        [str(organization_id), str(project_id), workbook_sha256, profile_sha256],
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _project_value(values: dict[str, Any], name: str) -> str | None:
    value = values.get(name)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _data_date(values: dict[str, Any]) -> date:
    value = values.get("data_date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is not None:
        normalized = str(value).strip()
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            try:
                return datetime.fromisoformat(
                    normalized.replace("Z", "+00:00")
                ).date()
            except ValueError:
                pass
    raise ControlCheckApplicationError(
        "invalid_project_metadata",
        "Workbook Project_Info must contain a valid data_date",
        422,
    )


def _is_dedupe_conflict(exc: IntegrityError) -> bool:
    diagnostic = getattr(getattr(exc, "orig", None), "diag", None)
    return getattr(diagnostic, "constraint_name", None) == DEDUPE_INDEX_NAME


class SnapshotIngestionService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: FileStorage,
        mapping_profile: MappingProfileV1,
        mpp_converter: Any | None = None,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.mapping_profile = mapping_profile
        self.mpp_converter = mpp_converter

    @staticmethod
    def _detached(
        session: Session,
        snapshot: GovernedDatasetSnapshotRecord,
    ) -> GovernedDatasetSnapshotRecord:
        if snapshot in session:
            session.expunge(snapshot)
        return snapshot

    def _reconcile_commit_outcome(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID | None,
        storage_key: str,
    ) -> GovernedDatasetSnapshotRecord | None:
        if snapshot_id is None:
            return None
        try:
            with self.session_factory() as session:
                snapshot = SnapshotRepository(session)._get_governed_scoped(
                    organization_id,
                    project_id,
                    snapshot_id,
                )
                if snapshot is None:
                    return None
                source = session.get(SourceFileRecord, snapshot.source_file_id)
                if (
                    snapshot.status in {"validated", "validated_with_errors"}
                    and source is not None
                    and source.organization_id == organization_id
                    and source.project_id == project_id
                    and source.storage_key == storage_key
                ):
                    return self._detached(session, snapshot)
        except ControlCheckApplicationError:
            raise
        except Exception as exc:
            raise ControlCheckApplicationError(
                "snapshot_commit_outcome_unknown",
                "Dataset snapshot commit outcome could not be reconciled",
                503,
            ) from exc
        raise ControlCheckApplicationError(
            "snapshot_commit_outcome_unknown",
            "Dataset snapshot commit outcome could not be reconciled",
            503,
        )

    def ingest(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
        force_new: bool = False,
    ) -> SnapshotIngestionResult:
        with self.session_factory() as session:
            project = ProjectRepository(session).get_scoped(
                organization_id, project_id
            )
        if project is None:
            raise ControlCheckApplicationError(
                "project_not_found",
                "Project was not found for this organization",
                404,
            )

        # Native MS Project binaries (.mpp/.mpx) are converted to the standard
        # workbook shape via MPXJ before the mapping-profile extraction runs.
        extract_data = data
        if filename.lower().endswith((".mpp", ".mpx")):
            if self.mpp_converter is None:
                raise ControlCheckApplicationError(
                    "mpp_requires_worker",
                    "MS Project (.mpp) uploads must be processed by the VPS "
                    "worker — the MPXJ converter is not available in this "
                    "serverless environment.",
                    400,
                )
            try:
                extract_data = self.mpp_converter.to_workbook_bytes(data, filename)
            except MppConversionError as exc:
                raise ControlCheckApplicationError(
                    "mpp_parse_failed", str(exc), 422
                ) from exc

        extracted = extract_workbook(extract_data, self.mapping_profile)
        # The selected ControlCheck project is the authoritative persistence
        # context. Source files exported from scheduling tools frequently do
        # not contain a project identifier, so derive the source metadata from
        # that context instead of rejecting an otherwise valid workbook.
        source_project_id = _project_value(extracted.project_values, "project_id") or project.code
        raw_source_project_name = extracted.project_values.get("project_name")
        source_project_name = (
            project.name
            if raw_source_project_name is None
            else str(raw_source_project_name)
        )
        if not source_project_name or not source_project_name.strip():
            source_project_name = project.name

        profile_sha = mapping_profile_sha256(self.mapping_profile)
        normal_dedupe_key = _dedupe_key(
            organization_id,
            project_id,
            extracted.workbook_sha256,
            profile_sha,
        )
        with self.session_factory() as session:
            repository = SnapshotRepository(session)
            profile_record = repository.resolve_mapping_profile(
                self.mapping_profile, profile_sha
            )
            duplicate = (
                None
                if force_new
                else repository.find_duplicate(
                    organization_id, project_id, normal_dedupe_key
                )
            )
            session.commit()
            profile_record_id = profile_record.id
            if duplicate is not None:
                return SnapshotIngestionResult(
                    snapshot=self._detached(session, duplicate),
                    outcome="deduplicated",
                )

        mapped = map_extracted_workbook(extracted, self.mapping_profile)
        if source_project_id != project.code:
            mapped = replace(
                mapped,
                warning_count=mapped.warning_count + 1,
                project_issues=(
                    *mapped.project_issues,
                    RowIssue(
                        code="source_project_mismatch",
                        message=(
                            f"Workbook source project {source_project_id} differs from "
                            f"target project {project.code}; target project is used for storage and analysis"
                        ),
                        field="project_id",
                        severity=IssueSeverity.warning,
                    ),
                ),
            )
        data_date = _data_date(extracted.project_values)
        dataset_version = (
            _project_value(extracted.project_values, "dataset_version")
            or self.mapping_profile.version
        )
        stored = self.storage.put(
            organization_id, project_id, filename, data
        )
        dedupe_key = None if force_new else normal_dedupe_key
        snapshot_id: UUID | None = None
        try:
            with self.session_factory() as session:
                repository = SnapshotRepository(session)
                snapshot = repository.create_ingesting(
                    organization_id=organization_id,
                    project_id=project_id,
                    filename=filename,
                    content_type=content_type,
                    stored=stored,
                    mapping_profile_version_id=profile_record_id,
                    dataset_version=dataset_version,
                    data_date=data_date,
                    source_project_id=source_project_id,
                    source_project_name=source_project_name,
                    dedupe_key=dedupe_key,
                )
                snapshot_id = snapshot.id
                raw_rows = repository.persist_raw_rows(
                    organization_id,
                    project_id,
                    snapshot.id,
                    extracted,
                    mapped,
                )
                repository.persist_canonical_rows(
                    organization_id,
                    project_id,
                    snapshot.id,
                    mapped,
                    raw_rows,
                )
                if not self.storage.exists(stored.key):
                    raise ControlCheckApplicationError(
                        "source_object_missing",
                        "Stored workbook could not be verified before snapshot completion",
                        500,
                    )
                completed = repository.complete(
                    organization_id,
                    project_id,
                    snapshot.id,
                    extracted,
                    mapped,
                )
                session.commit()
        except IntegrityError as exc:
            reconciled = self._reconcile_commit_outcome(
                organization_id,
                project_id,
                snapshot_id,
                stored.key,
            )
            if reconciled is not None:
                return SnapshotIngestionResult(
                    snapshot=reconciled,
                    outcome="created",
                )
            self.storage.delete(stored.key)
            if dedupe_key is not None and _is_dedupe_conflict(exc):
                with self.session_factory() as session:
                    winner = SnapshotRepository(session).find_duplicate(
                        organization_id, project_id, dedupe_key
                    )
                    if winner is not None:
                        return SnapshotIngestionResult(
                            snapshot=self._detached(session, winner),
                            outcome="deduplicated",
                        )
            raise
        except Exception:
            reconciled = self._reconcile_commit_outcome(
                organization_id,
                project_id,
                snapshot_id,
                stored.key,
            )
            if reconciled is not None:
                return SnapshotIngestionResult(
                    snapshot=reconciled,
                    outcome="created",
                )
            self.storage.delete(stored.key)
            raise
        return SnapshotIngestionResult(
            snapshot=self._detached(session, completed),
            outcome="created",
        )


__all__ = ["SnapshotIngestionResult", "SnapshotIngestionService"]
