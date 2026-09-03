"""Celery task definitions for the ControlCheck VPS worker."""

from __future__ import annotations

import logging
from uuid import UUID

from .celery_app import celery_app
from .executor import AnalysisJobExecutor, JobError, build_worker_dependencies

logger = logging.getLogger(__name__)

_executor: AnalysisJobExecutor | None = None


def _get_executor() -> AnalysisJobExecutor:
    global _executor
    if _executor is None:
        session_factory, storage, service = build_worker_dependencies()
        _executor = AnalysisJobExecutor(session_factory, storage, service)
        logger.info("Worker dependencies built (storage=%s)", type(storage).__name__)
    return _executor


@celery_app.task(
    name="controlcheck.worker.process_job",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_job(self, job_id: str) -> dict:
    """Claim and run one queued analysis job. Retries transient failures with
    exponential backoff; permanent failures are recorded on the job row."""
    try:
        run = _get_executor().execute(UUID(job_id))
    except JobError as exc:
        logger.warning("Job %s not executable: %s", job_id, exc)
        return {"job_id": job_id, "status": "skipped", "reason": str(exc)}
    except Exception as exc:
        logger.exception("Job %s failed (attempt %s)", job_id, self.request.retries + 1)
        if self.request.retries >= self.max_retries:
            _fail_job_permanently(job_id, exc)
            return {"job_id": job_id, "status": "failed", "reason": str(exc)}
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)
    return {
        "job_id": job_id,
        "status": "completed",
        "analysis_run_id": str(run.id) if run is not None else None,
    }


def _fail_job_permanently(job_id: str, exc: Exception) -> None:
    try:
        with _get_executor().session_factory() as session:
            from ..persistence.job_repository import AnalysisJobRepository

            AnalysisJobRepository(session).mark_failed(
                UUID(job_id), "analysis_failed", f"{type(exc).__name__}: {exc}"
            )
    except Exception:
        logger.exception("Could not mark job %s failed permanently", job_id)


@celery_app.task(name="controlcheck.worker.poll_queued_jobs")
def poll_queued_jobs() -> dict:
    """Beat poller: enqueue up to ``limit`` queued jobs per tick."""
    executor = _get_executor()
    limit = 4
    with executor.session_factory() as session:
        from ..persistence.job_repository import AnalysisJobRepository

        job_ids = AnalysisJobRepository(session).list_queued_ids(limit=limit)
    dispatched = 0
    for job_id in job_ids:
        process_job.delay(str(job_id))
        dispatched += 1
    if dispatched:
        logger.info("Polled %d queued job(s) into Celery", dispatched)
    return {"polled": dispatched}


@celery_app.task(name="controlcheck.worker.recover_stale_jobs")
def recover_stale_jobs() -> dict:
    """Beat task: requeue ``processing`` jobs whose worker died mid-flight."""
    recovered = _get_executor().recover_stale(grace_minutes=30)
    if recovered:
        logger.warning("Recovered %d stale job(s) back to queued", recovered)
    return {"recovered": recovered}
