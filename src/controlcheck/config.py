from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .versioning import ArtifactVersion


class RuleDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    name: str
    category: str
    severity: str
    objective: str
    inputs: str
    logic: str
    threshold: str
    evidence: str
    finding: str
    impact: str
    recommendation: str
    false_positive: str
    acceptance: str


class RuleCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    rules: list[RuleDefinition]

    def by_id(self, rule_id: str) -> RuleDefinition:
        for rule in self.rules:
            if rule.code == rule_id:
                return rule
        raise KeyError(f"Unknown rule: {rule_id}")


class SeverityBand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    severity: str
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    metric: str | None = None


class ExceptionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exception_id: str
    description: str
    conditions: dict[str, Any]


class RuleRuntimeV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_grain: Literal[
        "project", "wbs", "vendor_wbs", "transaction", "activity", "period_wbs"
    ]
    operator: str
    thresholds: dict[str, float | int]
    severity_bands: list[SeverityBand]
    lookback_periods: int | None = None
    materiality: dict[str, Decimal] = Field(default_factory=dict)
    exclusions: list[ExceptionSpec] = Field(default_factory=list)


class RuleDefinitionV2(RuleDefinition):
    runtime: RuleRuntimeV2


class RuleCatalogueV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    rules: list[RuleDefinitionV2]

    def by_id(self, rule_id: str) -> RuleDefinitionV2:
        for rule in self.rules:
            if rule.code == rule_id:
                return rule
        raise KeyError(f"Unknown rule: {rule_id}")


class ThresholdConfig(BaseModel):
    cost_spike_multiplier: float = 1.30
    cost_spike_materiality_bac: float = 0.01
    vendor_concentration_warning: float = 0.40
    vendor_concentration_critical: float = 0.60
    transaction_wbs_share: float = 0.05
    transaction_project_share: float = 0.02
    progress_lag_pp: float = 0.10
    cost_progress_cost_pct: float = 0.80
    cost_progress_max_progress: float = 0.50
    schedule_slippage_days: int = 7
    critical_progress_lag_pp: float = 0.20
    rising_cost_change_pct: float = 0.20
    flat_progress_change_pp: float = 0.02
    cross_domain_exposure_pct: float = 0.80


def load_catalogue(path: Path | str) -> RuleCatalogue | RuleCatalogueV2:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    version = ArtifactVersion.parse(payload.get("version", "")).major_minor
    if version == "0.1":
        return RuleCatalogue.model_validate(payload)
    if version == "0.2":
        return RuleCatalogueV2.model_validate(payload)
    raise ValueError(f"Unsupported rule catalogue version: {payload.get('version')!r}")
