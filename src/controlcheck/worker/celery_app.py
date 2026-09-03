"""Celery application for the ControlCheck VPS worker.

Run with (worker + beat scheduler in one process):

    celery -A controlcheck.worker.celery_app:celery_app worker -B \
        --concurrency=2 --loglevel=INFO

Broker (Redis) URL comes from ``CONTROLCHECK_REDIS_URL`` and defaults to a
local Redis on 6379 (matching the bundled docker-compose.worker.yml).
"""

from __future__ import annotations

import os

from celery import Celery

celery_app = Celery(
    "controlcheck",
    broker=os.environ.get("CONTROLCHECK_REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CONTROLCHECK_REDIS_URL", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # hard ceiling: 1 hour per workbook analysis
    task_soft_time_limit=3540,
    worker_max_tasks_per_child=20,  # recycle workers to bound memory growth
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    beat_schedule={
        "poll-queued-jobs-every-10s": {
            "task": "controlcheck.worker.poll_queued_jobs",
            "schedule": 10.0,
        },
        "recover-stale-jobs-every-5m": {
            "task": "controlcheck.worker.recover_stale_jobs",
            "schedule": 300.0,
        },
    },
)

# Ensure tasks are registered on the worker and under ``celery -B``.
from . import tasks  # noqa: E402,F401  (imports celery_app — safe, defined above)
