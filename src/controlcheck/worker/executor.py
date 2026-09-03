"""Durable-job executor: downloads a queued workbook from object storage and
runs the full deterministic analysis pipeline on the VPS worker."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

from ..application import AnalysisService
from ..persistence.database import create_session_factory
from ..persistence.job_repository import AnalysisJobRepository
from ..storage import FileStorage

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


class JobError(RuntimeError):
    """Raised when a job can no longer be retried (permanent failure)."""


class JobNotFound(JobError):
    pass


def _default_catalogue() -> Path:
    configured = os.environ.get("CONTROLCHECK_CATALOGUE")
    if configured:
        return Path(configured)
    data_dir = Path(__file__).resolve().parents[3] / "data"
    v02 = data_dir / "controlcheck_rule_catalogue_v0.2.json"
    if v02.exists():
        return v02
    return data_dir / "controlcheck_rule_catalogue_v0.1.json"


def _build_storage() -> FileStorage:
    backend = os.environ.get("CONTROLCHECK_STORAGE_BACKEND", "local")
    if backend == "s3":
        from ..storage_s3 import S3FileStorage

        return S3FileStorage(
            bucket=os.environ.get("CONTROLCHECK_S3_BUCKET", ""),
            region=os.environ.get("CONTROLCHECK_S3_REGION", "auto"),
            endpoint_url=os.environ.get("CONTROLCHECK_S3_ENDPOINT_URL") or None,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
        )
    upload_root = Path(os.environ.get("CONTROLCHECK_UPLOAD_ROOT", "var/uploads"))
    from ..storage import LocalFileStorage

    return LocalFileStorage(upload_root)


def build_worker_dependencies() -> tuple["sessionmaker[Session]", FileStorage, AnalysisService]:
    """Recreate the same runtime wiring as the API app, from environment."""
    from ..settings import ProductionSettings

    settings = ProductionSettings.from_env()
    if not settings.database_url:
        raise RuntimeError("CONTROLCHECK_DATABASE_URL is required for the worker")
    session_factory = create_session_factory(settings.database_url)
    storage = _build_storage()
    from ..ingestion.mpp_converter import build_mpp_converter

    service = AnalysisService(
        session_factory,
        storage,
        _default_catalogue(),
        mpp_converter=build_mpp_converter(),
    )
    return session_factory, storage, service


class AnalysisJobExecutor:
    """Claims analysis_jobs rows and executes the heavy pipeline.

    Concurrency is bounded by the Celery worker (``--concurrency``); each
    execution holds one workbook in memory. Use 1-2 workers on an 8 GB VPS.
    """

    def __init__(
        self,
        session_factory: "sessionmaker[Session]",
        storage: FileStorage,
        analysis_service: AnalysisService,
    ):
        self.session_factory = session_factory
        self.storage = storage
        self.analysis_service = analysis_service

    def execute(self, job_id: UUID):
        """Claim and execute one queued job. Idempotent: a job that is already
        completed is a no-op; a job already claimed raises JobError."""
        with self.session_factory() as session:
            repository = AnalysisJobRepository(session)
            claimed = repository.claim_job(job_id)
            if claimed is None:
                existing = repository.get_job_by_id(job_id)
                if existing is not None and existing.status == "completed":
                    logger.info("Job %s already completed — skipping", job_id)
                    return None
                raise JobError(f"Job {job_id} is not queued (status already claimed)")
            job = claimed

        logger.info(
            "Job %s claimed: %s (%d bytes) — downloading from storage",
            job.id, job.filename, job.file_size_bytes,
        )
        data = self.storage.get(job.storage_key)

        try:
            run = self.analysis_service.run(
                job.organization_id,
                job.project_id,
                job.filename,
                job.content_type,
                data,
            )
        except Exception as exc:
            with self.session_factory() as session:
                repository = AnalysisJobRepository(session)
                if job.attempts >= MAX_ATTEMPTS:
                    repository.mark_failed(
                        job.id, "analysis_failed", f"{type(exc).__name__}: {exc}"
                    )
                    logger.exception("Job %s permanently failed", job.id)
                else:
                    # Release back to the queue for a later retry.
                    repository.requeue(job.id)
                    logger.warning("Job %s requeued after failure: %s", job.id, exc)
            raise

        # Success: persist completion, then remove the transient upload copy.
        with self.session_factory() as session:
            AnalysisJobRepository(session).mark_completed(job.id, run.id)
        try:
            self.storage.delete(job.storage_key)
            logger.info("Job %s: transient upload copy %s deleted", job.id, job.storage_key)
        except Exception:
            logger.warning("Job %s: could not delete transient copy %s", job.id, job.storage_key)
        logger.info("Job %s completed — analysis run %s", job.id, run.id)
        return run

    def recover_stale(self, grace_minutes: int = 30) -> int:
        """Reset ``processing`` jobs whose worker died back to ``queued``."""
        with self.session_factory() as session:
            return AnalysisJobRepository(session).recover_stale(grace_minutes)
