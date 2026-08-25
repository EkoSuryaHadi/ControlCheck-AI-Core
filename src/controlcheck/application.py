from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from . import __version__
from .config import ThresholdConfig, load_catalogue
from .engine import ControlEngine, RuleContext
from .errors import ControlCheckApplicationError
from .ingestion.profile import load_mapping_profile
from .ingestion.service import SnapshotIngestionService
from .loader import WorkbookSchemaError, load_workbook
from .logging import get_logger, set_log_context
from .models import AuditResult
from .persistence.dataset_loader import DatabaseDatasetLoader
from .persistence.models import AnalysisRunRecord
from .persistence.repositories import AnalysisRepository, ProjectRepository
from .rules import ALL_RULES
from .service import run_audit
from .storage import FileStorage
from .versioning import VersionCompatibilityError

logger = get_logger("application")



class AnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage: FileStorage,
        catalogue_path: Path | str,
        audit_runner: Callable[..., AuditResult] | None = None,
        engine: ControlEngine | None = None,
        mapping_profile_path: Path | str | None = None,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.catalogue_path = Path(catalogue_path)
        self.audit_runner = audit_runner
        self.engine = engine or ControlEngine(ALL_RULES)
        self.mapping_profile_path = (
            Path(mapping_profile_path)
            if mapping_profile_path
            else self.catalogue_path.parent
            / "controlcheck_mapping_profile_v0.1.json"
        )

    def _run_legacy(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
        idempotency_key: str | None = None,
    ):
        set_log_context(organization_id=str(organization_id), project_id=str(project_id))
        logger.info("Initiating analysis run for project %s (file: %s, size: %d bytes, idempotency_key: %s)", project_id, filename, len(data), idempotency_key)
        
        if idempotency_key:
            with self.session_factory() as session:
                existing_run = AnalysisRepository(session).get_run_by_idempotency_key(
                    organization_id, project_id, idempotency_key
                )
                if existing_run is not None:
                    logger.info("Idempotency match found for key %s, returning existing run %s", idempotency_key, existing_run.id)
                    return existing_run

        with self.session_factory() as session:
            project = ProjectRepository(session).get_scoped(organization_id, project_id)

        if project is None:
            logger.warning("Analysis rejected: project %s not found for org %s", project_id, organization_id)
            raise ControlCheckApplicationError(
                "project_not_found", "Project was not found for this organization", 404
            )

        stored = self.storage.put(organization_id, project_id, filename, data)
        try:
            dataset = load_workbook(BytesIO(data))
        except WorkbookSchemaError as exc:
            logger.warning("Workbook schema validation error: %s", exc)
            self.storage.delete(stored.key)
            raise ControlCheckApplicationError(exc.code, str(exc), 422) from exc
        if dataset.project.project_id != project.code:
            logger.warning(
                "Workbook project code '%s' does not match registered project code '%s'",
                dataset.project.project_id,
                project.code,
            )
            self.storage.delete(stored.key)
            raise ControlCheckApplicationError(
                "workbook_project_mismatch",
                (
                    f"Workbook Project ID '{dataset.project.project_id}' does not match "
                    f"the active ControlCheck project code '{project.code}'. "
                    "Select the matching project or update the workbook Project sheet before ingestion."
                ),
                422,
            )

        from .ingestion.raw_store import extract_raw_rows
        raw_items = extract_raw_rows(BytesIO(data))

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
                    raw_items=raw_items,
                )
                session.commit()
                set_log_context(analysis_run_id=str(run.id))
                logger.info("Created analysis run record %s (status=running)", run.id)
            except Exception:

                session.rollback()
                self.storage.delete(stored.key)
                logger.exception("Failed to initialize analysis run record in database")
                raise

        started = perf_counter()
        try:
            audit = self.audit_runner(BytesIO(data), self.catalogue_path)
        except VersionCompatibilityError as exc:
            logger.warning("Analysis failed due to version compatibility: %s", exc)
            return self._persist_failure(run.id, exc.code, str(exc), 422, started, exc)
        except WorkbookSchemaError as exc:
            logger.warning("Analysis failed due to workbook schema error: %s", exc)
            return self._persist_failure(run.id, exc.code, str(exc), 422, started, exc)
        except Exception as exc:
            logger.exception("Unexpected error during audit engine execution")
            return self._persist_failure(
                run.id, "analysis_failed", "Analysis could not be completed", 500, started, exc
            )

        duration_ms = max(0, round((perf_counter() - started) * 1000))
        with self.session_factory() as session:
            repository = AnalysisRepository(session)
            completed = repository.complete_run(run.id, audit, duration_ms)

            # Compute and persist health snapshot
            from .health.scoring import compute_health_score
            health_result = compute_health_score(audit.findings)
            from .persistence.repositories import HealthRepository
            HealthRepository(session).create_snapshot(
                organization_id=organization_id,
                project_id=project_id,
                analysis_run_id=completed.id,
                overall_score=health_result.overall_score,
                cost_score=health_result.category_scores["COST"].score,
                schedule_score=health_result.category_scores["SCHEDULE"].score,
                progress_score=health_result.category_scores["PROGRESS"].score,
                dq_score=health_result.category_scores["DATA_QUALITY"].score,
                score_band=health_result.score_band,
                component_breakdown=health_result.component_breakdown,
                key_drivers=[d.__dict__ for d in health_result.top_drivers],
                score_version=health_result.score_version,
            )

            if idempotency_key:
                repository.record_idempotency(
                    organization_id, project_id, completed.id, idempotency_key
                )
            session.commit()
            logger.info(
                "Analysis run %s completed successfully in %d ms with %d findings (health score: %.2f - %s)",
                run.id,
                duration_ms,
                audit.finding_count,
                health_result.overall_score,
                health_result.score_band,
            )
            return completed

    def run_snapshot(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        *,
        idempotency_key: str | None = None,
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
                catalogue_definition["version"],
                catalogue_sha,
                catalogue_definition,
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
                RuleContext(
                    catalogue=catalogue_runtime,
                    thresholds=ThresholdConfig(),
                ),
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
                repository = AnalysisRepository(session)
                completed = repository.complete_run(
                    run.id,
                    execution.audit,
                    duration_ms,
                    executed_rule_ids=list(execution.executed_rule_ids),
                    skipped_rules=skipped_rules,
                    raw_row_index=loaded.raw_row_index,
                )

                from .health.scoring import compute_health_score
                from .persistence.repositories import HealthRepository

                health_result = compute_health_score(execution.audit.findings)
                HealthRepository(session).create_snapshot(
                    organization_id=organization_id,
                    project_id=project_id,
                    analysis_run_id=completed.id,
                    overall_score=health_result.overall_score,
                    cost_score=health_result.category_scores["COST"].score,
                    schedule_score=health_result.category_scores["SCHEDULE"].score,
                    progress_score=health_result.category_scores["PROGRESS"].score,
                    dq_score=health_result.category_scores["DATA_QUALITY"].score,
                    score_band=health_result.score_band,
                    component_breakdown=health_result.component_breakdown,
                    key_drivers=[
                        driver.__dict__ for driver in health_result.top_drivers
                    ],
                    score_version=health_result.score_version,
                )
                if idempotency_key:
                    repository.record_idempotency(
                        organization_id,
                        project_id,
                        completed.id,
                        idempotency_key,
                    )
                session.commit()
                return completed
        except Exception as exc:
            reconciled = self._reconcile_analysis_commit(
                organization_id,
                project_id,
                snapshot_id,
                run.id,
            )
            if reconciled is not None:
                return reconciled
            return self._persist_failure(
                run.id,
                "analysis_failed",
                "Analysis could not be completed",
                500,
                started,
                exc,
            )

    def _reconcile_analysis_commit(
        self,
        organization_id: UUID,
        project_id: UUID,
        snapshot_id: UUID,
        run_id: UUID,
    ):
        try:
            with self.session_factory() as session:
                run = session.scalar(
                    select(AnalysisRunRecord).where(
                        AnalysisRunRecord.id == run_id,
                        AnalysisRunRecord.organization_id == organization_id,
                        AnalysisRunRecord.project_id == project_id,
                        AnalysisRunRecord.governed_dataset_snapshot_id
                        == snapshot_id,
                    )
                )
                if run is None:
                    raise ControlCheckApplicationError(
                        "analysis_commit_outcome_unknown",
                        "Analysis commit outcome could not be reconciled",
                        503,
                        analysis_run_id=run_id,
                    )
                if run.status == "running":
                    return None
                if run.status == "succeeded":
                    session.expunge(run)
                    return run
        except ControlCheckApplicationError:
            raise
        except Exception as exc:
            raise ControlCheckApplicationError(
                "analysis_commit_outcome_unknown",
                "Analysis commit outcome could not be reconciled",
                503,
                analysis_run_id=run_id,
            ) from exc
        raise ControlCheckApplicationError(
            "analysis_commit_outcome_unknown",
            "Analysis commit outcome could not be reconciled",
            503,
            analysis_run_id=run_id,
        )

    def run(
        self,
        organization_id: UUID,
        project_id: UUID,
        filename: str,
        content_type: str,
        data: bytes,
        idempotency_key: str | None = None,
    ):
        if idempotency_key:
            with self.session_factory() as session:
                existing_run = AnalysisRepository(
                    session
                ).get_run_by_idempotency_key(
                    organization_id, project_id, idempotency_key
                )
                if existing_run is not None:
                    return existing_run
        ingestion = SnapshotIngestionService(
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
        snapshot = ingestion.snapshot
        return self.run_snapshot(
            organization_id,
            project_id,
            snapshot.id,
            idempotency_key=idempotency_key,
        )



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
        logger.error("Analysis run %s marked failed with code '%s' (%d ms)", run_id, code, duration_ms)
        with self.session_factory() as session:
            AnalysisRepository(session).fail_run(run_id, code, safe_message, duration_ms)
            session.commit()
        raise ControlCheckApplicationError(
            code, safe_message, status_code, analysis_run_id=run_id
        ) from cause
