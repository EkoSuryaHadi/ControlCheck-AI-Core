from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from .models import ProjectDataset


def _status(value: object) -> str:
    return str(getattr(value, "value", value) or "blocked")


def _average(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def summarize_dataset(
    dataset: ProjectDataset,
    domain_statuses: Mapping[str, object],
) -> dict:
    """Return a JSON-safe, factual overview of one governed dataset snapshot."""
    schedule = list(dataset.schedule)
    explicit_progress = list(dataset.progress)
    budget_total = float(sum((row.budget_amount for row in dataset.budgets), start=0))
    actual_total = float(sum((row.actual_amount for row in dataset.actual_costs), start=0))
    commitment_total = float(sum((row.committed_amount for row in dataset.commitments), start=0))

    activity_rows = [
        {
            "activity_id": row.activity_id,
            "activity_name": row.activity_name,
            "wbs_code": row.wbs_code,
            "baseline_finish": row.baseline_finish.isoformat(),
            "actual_finish": row.actual_finish.isoformat() if row.actual_finish else None,
            "planned_progress": row.planned_progress,
            "actual_progress": row.actual_progress,
            "total_float_days": row.total_float_days,
            "critical": row.critical,
            "status": row.status,
        }
        for row in sorted(
            schedule,
            key=lambda item: (item.total_float_days >= 0, -item.total_float_days, item.activity_id),
        )[:100]
    ]

    if explicit_progress:
        progress_source = "progress"
        planned_progress = _average([row.planned_progress for row in explicit_progress])
        actual_progress = _average([row.actual_progress for row in explicit_progress])
    elif schedule:
        progress_source = "schedule_derived"
        planned_progress = _average([row.planned_progress for row in schedule])
        actual_progress = _average([row.actual_progress for row in schedule])
    else:
        progress_source = "unavailable"
        planned_progress = actual_progress = 0.0

    return {
        "domains": {domain: _status(value) for domain, value in domain_statuses.items()},
        "cost": {
            "available": bool(dataset.budgets or dataset.actual_costs or dataset.commitments),
            "budget_total": budget_total,
            "actual_total": actual_total,
            "commitment_total": commitment_total,
        },
        "schedule": {
            "activity_count": len(schedule),
            "critical_count": sum(row.critical for row in schedule),
            "negative_float_count": sum(row.total_float_days < 0 for row in schedule),
            "high_float_count": sum(row.total_float_days > 20 for row in schedule),
            "activities": activity_rows,
        },
        "progress": {
            "available": bool(explicit_progress or schedule),
            "source": progress_source,
            "planned_progress": planned_progress,
            "actual_progress": actual_progress,
            "variance": round(actual_progress - planned_progress, 4),
        },
    }
