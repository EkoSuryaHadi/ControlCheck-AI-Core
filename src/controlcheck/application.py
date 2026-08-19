from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .config import ThresholdConfig, load_catalogue
from .engine import ControlEngine, RuleContext
from .errors import ControlCheckApplicationError
from .ingestion.profile import load_mapping_profile
from .ingestion.service import SnapshotIngestionService
from .persistence.repositories import AnalysisRepository
from .persistence.dataset_loader import DatabaseDatasetLoader
from .rules import ALL_RULES
from .storage import FileStorage


class AnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: FileStorage,
        catalogue_path: Path | str,
        engine: ControlEngine | None = None,
        mapping_profile_path: Path | str | None = None,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.catalogue_path = Path(catalogue_path)
        self.engine = engine or ControlEngine(ALL_RULES)
        self.mapping_profile_path = Path(mapping_profile_path) if mapping_profile_path else (
            self.catalogue_path.parent / "controlcheck_mapping_profile_v0.1.json"
        )

    def run_snapshot(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
    ):
        loaded = DatabaseDatasetLoader(self.session_factory).load(
            organization_id, project_id, snapshot_id
        )
        catalogue_bytes = self.catalogue_path.read_bytes()
        catalogue_definition = json.loads(catalogue_bytes.decode("utf-8"))
        catalogue_sha = hashlib.sha256(catalogue_bytes).hexdigest()
        catalogue_runtime = load_catalogue(self.catalogue_path)
        with self.session_factory() as session:
            repository = AnalysisRepository(session)
            catalogue = repository.get_or_create_catalogue(
                catalogue_definition["version"], catalogue_sha, catalogue_definition
            )
            run = repository.start_snapshot_run(
                organization_id,
                project_id,
                snapshot_id,
                catalogue,
                __version__,
            )
            session.commit()

        started = perf_counter()
        try:
            execution = self.engine.run_gated(
                loaded.snapshot,
                RuleContext(catalogue=catalogue_runtime, thresholds=ThresholdConfig()),
                loaded.domain_statuses,
            )
            duration_ms = max(0, round((perf_counter() - started) * 1000))
            skipped_rules = [
                {
                    "rule_id": item.rule_id,
                    "reason_code": item.reason_code,
                    "blocked_domains": list(item.blocked_domains),
                }
                for item in execution.skipped_rules
            ]
            with self.session_factory() as session:
                completed = AnalysisRepository(session).complete_run(
                    run.id,
                    execution.audit,
                    duration_ms,
                    executed_rule_ids=list(execution.executed_rule_ids),
                    skipped_rules=skipped_rules,
                    raw_row_index=loaded.raw_row_index,
                )
                session.commit()
                return completed
        except Exception as exc:
            return self._persist_failure(
                run.id,
                "analysis_failed",
                "Analysis could not be completed",
                500,
                started,
                exc,
            )

    def run(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
    ):
        snapshot = SnapshotIngestionService(
            self.session_factory,
            self.storage,
            load_mapping_profile(self.mapping_profile_path),
        ).ingest(
            organization_id,
            project_id,
            filename,
            content_type,
            data,
        )
        return self.run_snapshot(organization_id, project_id, snapshot.id)

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
