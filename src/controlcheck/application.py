from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .errors import ControlCheckApplicationError
from .loader import WorkbookSchemaError, load_workbook
from .models import AuditResult
from .persistence.repositories import AnalysisRepository, ProjectRepository
from .service import run_audit
from .storage import FileStorage
from .versioning import VersionCompatibilityError


class AnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: FileStorage,
        catalogue_path: Path | str,
        audit_runner: Callable[..., AuditResult] | None = None,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.catalogue_path = Path(catalogue_path)
        self.audit_runner = audit_runner or run_audit

    def run(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ):
        with self.session_factory() as session:
            project = ProjectRepository(session).get_scoped(organization_id, project_id)
        if project is None:
            raise ControlCheckApplicationError(
                "project_not_found", "Project was not found for this organization", 404
            )

        stored = self.storage.put(organization_id, project_id, filename, data)
        try:
            dataset = load_workbook(BytesIO(data))
        except WorkbookSchemaError as exc:
            self.storage.delete(stored.key)
            raise ControlCheckApplicationError(exc.code, str(exc), 422) from exc
        if dataset.project.project_id != project.code:
            self.storage.delete(stored.key)
            raise ControlCheckApplicationError(
                "workbook_project_mismatch",
                "Workbook project ID does not match the target project code",
                422,
            )

        catalogue_bytes = self.catalogue_path.read_bytes()
        catalogue_definition = json.loads(catalogue_bytes.decode("utf-8"))
        catalogue_sha = hashlib.sha256(catalogue_bytes).hexdigest()
        with self.session_factory() as session:
            repository = AnalysisRepository(session)
            try:
                catalogue = repository.get_or_create_catalogue(
                    catalogue_definition["version"], catalogue_sha, catalogue_definition
                )
                run = repository.start_run(
                    organization_id,
                    project_id,
                    filename,
                    content_type,
                    stored,
                    dataset,
                    catalogue,
                    __version__,
                )
                session.commit()
            except Exception:
                session.rollback()
                self.storage.delete(stored.key)
                raise

        started = perf_counter()
        try:
            audit = self.audit_runner(BytesIO(data), self.catalogue_path)
        except VersionCompatibilityError as exc:
            return self._persist_failure(run.id, exc.code, str(exc), 422, started, exc)
        except WorkbookSchemaError as exc:
            return self._persist_failure(run.id, exc.code, str(exc), 422, started, exc)
        except Exception as exc:
            return self._persist_failure(
                run.id, "analysis_failed", "Analysis could not be completed", 500, started, exc
            )

        duration_ms = max(0, round((perf_counter() - started) * 1000))
        with self.session_factory() as session:
            repository = AnalysisRepository(session)
            completed = repository.complete_run(run.id, audit, duration_ms)
            session.commit()
            return completed

    def _persist_failure(
        self,
        run_id: UUID,
        code: str,
        safe_message: str,
        status_code: int,
        started: float,
        cause: Exception,
    ):
        duration_ms = max(0, round((perf_counter() - started) * 1000))
        with self.session_factory() as session:
            AnalysisRepository(session).fail_run(run_id, code, safe_message, duration_ms)
            session.commit()
        raise ControlCheckApplicationError(
            code, safe_message, status_code, analysis_run_id=run_id
        ) from cause
