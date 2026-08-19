from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..errors import ControlCheckApplicationError
from ..persistence.ingestion_repositories import SnapshotRepository
from ..persistence.models import DatasetSnapshotRecord
from ..persistence.repositories import ProjectRepository
from ..storage import FileStorage
from .extractor import extract_workbook
from .mapper import map_extracted_workbook
from .profile import MappingProfileV1, mapping_profile_sha256


DEDUPE_INDEX_NAME = "ux_dataset_snapshots_dedupe_key_not_null"


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
                return datetime.fromisoformat(normalized.replace("Z", "+00:00")).date()
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
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.mapping_profile = mapping_profile

    @staticmethod
    def _detached(session: Session, snapshot: DatasetSnapshotRecord) -> DatasetSnapshotRecord:
        if snapshot in session:
            session.expunge(snapshot)
        return snapshot

    def ingest(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
        force_new: bool = False,
    ) -> DatasetSnapshotRecord:
        with self.session_factory() as session:
            project = ProjectRepository(session).get_scoped(organization_id, project_id)
        if project is None:
            raise ControlCheckApplicationError(
                "project_not_found",
                "Project was not found for this organization",
                404,
            )

        extracted = extract_workbook(data, self.mapping_profile)
        source_project_id = _project_value(extracted.project_values, "project_id")
        if source_project_id is None:
            raise ControlCheckApplicationError(
                "invalid_project_metadata",
                "Workbook Project_Info must contain project_id",
                422,
            )
        if source_project_id != project.code:
            raise ControlCheckApplicationError(
                "workbook_project_mismatch",
                "Workbook project ID does not match the target project code",
                422,
            )
        raw_source_project_name = extracted.project_values.get("project_name")
        source_project_name = (
            None if raw_source_project_name is None else str(raw_source_project_name)
        )
        if source_project_name is None or not source_project_name.strip():
            raise ControlCheckApplicationError(
                "invalid_project_metadata",
                "Workbook Project_Info must contain project_name",
                422,
            )

        profile_sha = mapping_profile_sha256(self.mapping_profile)
        normal_dedupe_key = _dedupe_key(
            organization_id,
            project_id,
            extracted.workbook_sha256,
            profile_sha,
        )
        with self.session_factory() as session:
            repository = SnapshotRepository(session)
            profile_record = repository.resolve_mapping_profile(self.mapping_profile, profile_sha)
            duplicate = None if force_new else repository.find_duplicate(
                organization_id, project_id, normal_dedupe_key
            )
            session.commit()
            profile_record_id = profile_record.id
            if duplicate is not None:
                return self._detached(session, duplicate)

        mapped = map_extracted_workbook(extracted, self.mapping_profile)
        data_date = _data_date(extracted.project_values)
        dataset_version = _project_value(extracted.project_values, "dataset_version") or self.mapping_profile.version
        stored = self.storage.put(organization_id, project_id, filename, data)
        dedupe_key = None if force_new else normal_dedupe_key

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
                raw_rows = repository.persist_raw_rows(
                    organization_id, project_id, snapshot.id, extracted, mapped
                )
                repository.persist_canonical_rows(
                    organization_id, project_id, snapshot.id, mapped, raw_rows
                )
                if not self.storage.exists(stored.key):
                    raise ControlCheckApplicationError(
                        "source_object_missing",
                        "Stored workbook could not be verified before snapshot completion",
                        500,
                    )
                completed = repository.complete(
                    organization_id, project_id, snapshot.id, extracted, mapped
                )
                session.commit()
        except IntegrityError as exc:
            self.storage.delete(stored.key)
            if dedupe_key is not None and _is_dedupe_conflict(exc):
                with self.session_factory() as session:
                    winner = SnapshotRepository(session).find_duplicate(
                        organization_id, project_id, dedupe_key
                    )
                    if winner is not None:
                        return self._detached(session, winner)
            raise
        except Exception:
            self.storage.delete(stored.key)
            raise
        return self._detached(session, completed)


__all__ = ["SnapshotIngestionService"]
