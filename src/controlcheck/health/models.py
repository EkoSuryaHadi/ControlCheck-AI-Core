from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScoreDriver:
    finding_id: str
    rule_id: str
    rule_name: str
    entity_id: str
    severity: str
    penalty: float
    description: str


@dataclass
class CategoryScore:
    category: str
    score: float
    weight: float
    weighted_score: float
    critical_count: int = 0
    warning_count: int = 0
    observation_count: int = 0
    drivers: list[ScoreDriver] = field(default_factory=list)


@dataclass
class HealthScoreResult:
    overall_score: float
    score_band: str
    score_version: str
    category_scores: dict[str, CategoryScore]
    top_drivers: list[ScoreDriver]
    component_breakdown: dict[str, Any]
