from __future__ import annotations

from typing import Any, Sequence
from .models import CategoryScore, HealthScoreResult, ScoreDriver
from ..logging import get_logger

logger = get_logger("health.scoring")

DEFAULT_WEIGHTS = {
    "COST": 0.30,
    "SCHEDULE": 0.30,
    "PROGRESS": 0.25,
    "DATA_QUALITY": 0.15,
}

SEVERITY_PENALTIES = {
    "critical": 15.0,
    "warning": 5.0,
    "observation": 1.0,
}


def determine_score_band(score: float) -> str:
    """Classifies health score into standard PRD score bands."""
    if score >= 80.0:
        return "Healthy"
    if score >= 60.0:
        return "Needs Attention"
    if score >= 40.0:
        return "At Risk"
    return "Critical"


def normalize_category(cat: str) -> str:
    cleaned = cat.upper().strip()
    if cleaned in {"DQ", "DATA QUALITY", "DATA_QUALITY"}:
        return "DATA_QUALITY"
    if cleaned in {"COST", "SCHEDULE", "PROGRESS"}:
        return cleaned
    if cleaned in {"CROSS_DOMAIN", "CROSS-DOMAIN", "CROSS DOMAIN"}:
        # Cross domain impacts cost & schedule
        return "COST"
    return "DATA_QUALITY"


def compute_health_score(
    findings: Sequence[Any],
    weights: dict[str, float] | None = None,
    score_version: str = "1.0",
) -> HealthScoreResult:
    """Computes transparent, reproducible project health score from findings."""
    active_weights = weights or DEFAULT_WEIGHTS
    logger.info("Computing health score across %d finding(s) with version %s", len(findings), score_version)

    # Initialize domain buckets
    buckets: dict[str, list[ScoreDriver]] = {cat: [] for cat in active_weights}
    counts: dict[str, dict[str, int]] = {
        cat: {"critical": 0, "warning": 0, "observation": 0}
        for cat in active_weights
    }

    for finding in findings:
        # Support both Finding pydantic models and FindingRecord ORM instances
        severity = getattr(finding, "severity", "warning").lower()
        raw_cat = getattr(finding, "category", "DATA_QUALITY")
        cat = normalize_category(raw_cat)
        if cat not in buckets:
            cat = "DATA_QUALITY"

        penalty = SEVERITY_PENALTIES.get(severity, 5.0)
        counts[cat][severity] = counts[cat].get(severity, 0) + 1

        finding_id = str(getattr(finding, "finding_id", getattr(finding, "engine_finding_id", getattr(finding, "id", ""))))
        rule_id = str(getattr(finding, "rule_id", ""))
        rule_name = str(getattr(finding, "rule_name", rule_id))
        entity_id = str(getattr(finding, "entity_id", ""))
        description = str(getattr(finding, "description", getattr(finding, "title", "")))

        driver = ScoreDriver(
            finding_id=finding_id,
            rule_id=rule_id,
            rule_name=rule_name,
            entity_id=entity_id,
            severity=severity,
            penalty=penalty,
            description=description,
        )
        buckets[cat].append(driver)

    category_scores: dict[str, CategoryScore] = {}
    weighted_total = 0.0

    for cat, weight in active_weights.items():
        domain_drivers = buckets[cat]
        domain_drivers.sort(key=lambda d: d.penalty, reverse=True)

        total_penalty = sum(d.penalty for d in domain_drivers)
        score = max(0.0, 100.0 - total_penalty)
        weighted = round(score * weight, 2)
        weighted_total += weighted

        category_scores[cat] = CategoryScore(
            category=cat,
            score=round(score, 2),
            weight=weight,
            weighted_score=weighted,
            critical_count=counts[cat]["critical"],
            warning_count=counts[cat]["warning"],
            observation_count=counts[cat]["observation"],
            drivers=domain_drivers[:5],
        )

    overall_score = round(min(100.0, max(0.0, weighted_total)), 2)
    band = determine_score_band(overall_score)

    all_drivers = [d for drivers in buckets.values() for d in drivers]
    all_drivers.sort(key=lambda d: d.penalty, reverse=True)
    top_drivers = all_drivers[:10]

    breakdown = {
        cat: {
            "score": cs.score,
            "weight": cs.weight,
            "weighted_score": cs.weighted_score,
            "critical_count": cs.critical_count,
            "warning_count": cs.warning_count,
            "observation_count": cs.observation_count,
        }
        for cat, cs in category_scores.items()
    }

    logger.info(
        "Health score computed: overall=%.2f (%s) [Cost: %.2f, Sched: %.2f, Prog: %.2f, DQ: %.2f]",
        overall_score,
        band,
        category_scores["COST"].score,
        category_scores["SCHEDULE"].score,
        category_scores["PROGRESS"].score,
        category_scores["DATA_QUALITY"].score,
    )

    return HealthScoreResult(
        overall_score=overall_score,
        score_band=band,
        score_version=score_version,
        category_scores=category_scores,
        top_drivers=top_drivers,
        component_breakdown=breakdown,
    )
